from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.chat.citations import parse_cited_chunks
from app.chat.confidence import ConfidenceAssessment, RetrievedChunk, assess_confidence
from app.chat.prompts import (
    GROUNDED_SYSTEM_PROMPT,
    build_context_block,
    build_low_confidence_response,
)
from app.chat.title import generate_title
from app.models.conversation import Conversation
from app.models.message import Message
from app.providers.embeddings import EmbeddingProvider
from app.providers.llm import ChatMessage, LLMProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


@dataclass
class RetrievalEvent:
    chunks: list[RetrievedChunk]
    top_similarity: float
    avg_similarity: float


@dataclass
class ConfidenceEvent:
    sufficient: bool
    reason: str
    top_similarity: float
    avg_similarity: float


@dataclass
class TokenEvent:
    text: str


@dataclass
class SourceInfo:
    chunk_id: str
    document_id: str
    filename: str
    text_preview: str
    score: float


@dataclass
class SourcesEvent:
    sources: list[SourceInfo]


@dataclass
class MessagePersistedEvent:
    conversation_id: UUID
    assistant_message_id: UUID


@dataclass
class ErrorEvent:
    message: str


@dataclass
class DoneEvent:
    pass


ChatEvent = (
    RetrievalEvent
    | ConfidenceEvent
    | TokenEvent
    | SourcesEvent
    | MessagePersistedEvent
    | ErrorEvent
    | DoneEvent
)


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


@dataclass
class ChatTurnInput:
    user_message: str
    conversation_id: UUID | None = None
    user_id: str = "dev"
    model_tier: Literal["default", "strong"] = "default"
    _skip_user_persist: bool = field(default=False, repr=False)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _retrieve_chunks(
    query: str,
    top_k: int,
    embedding_provider: EmbeddingProvider,
    session_factory: Callable[[], AsyncSession],
) -> list[RetrievedChunk]:
    vectors = await embedding_provider.embed([query])
    vec = vectors[0]
    vec_str = "[" + ",".join(str(v) for v in vec) + "]"

    sql = text("""
        SELECT
            c.id,
            c.document_id,
            d.filename,
            c.chunk_index,
            c.text,
            1 - (c.embedding <=> CAST(:vec AS vector)) AS score,
            c.token_count
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.embedding IS NOT NULL AND d.deleted_at IS NULL
        ORDER BY c.embedding <=> CAST(:vec AS vector)
        LIMIT :limit
    """)

    async with session_factory() as session:
        result = await session.execute(sql, {"vec": vec_str, "limit": top_k})
        rows = result.all()

    return [
        RetrievedChunk(
            chunk_id=str(row.id),
            document_id=str(row.document_id),
            filename=row.filename,
            chunk_index=row.chunk_index,
            text=row.text,
            score=float(row.score),
            token_count=row.token_count,
        )
        for row in rows
    ]


async def _count_messages(conversation_id: UUID, session_factory: Callable[[], AsyncSession]) -> int:
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM messages WHERE conversation_id = :cid"),
            {"cid": str(conversation_id)},
        )
        return result.scalar() or 0


async def _save_title(
    conversation_id: UUID,
    user_message: str,
    llm_provider: LLMProvider,
    session_factory: Callable[[], AsyncSession],
) -> None:
    title = await generate_title(user_message, llm_provider)
    async with session_factory() as session:
        conv = await session.get(Conversation, conversation_id)
        if conv is not None and conv.title is None:
            conv.title = title
            session.add(conv)
            await session.commit()
    logger.info("conversation_id=%s title=%r", conversation_id, title)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def run_chat_turn(
    input: ChatTurnInput,
    session_factory: Callable[[], AsyncSession],
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
    top_k: int = 8,
    min_top_similarity: float = 0.25,
    min_avg_similarity: float = 0.20,
    avg_window: int = 5,
    max_context_chunks: int = 8,
    max_output_tokens: int = 2048,
) -> AsyncGenerator[ChatEvent, None]:
    # 1. Get or create conversation
    async with session_factory() as session:
        if input.conversation_id is None:
            conv = Conversation(user_id=input.user_id)
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
            conversation_id = conv.id
            is_new_conversation = True
        else:
            conversation_id = input.conversation_id
            is_new_conversation = False

    # 2. Persist user message
    if not input._skip_user_persist:
        msg_count = await _count_messages(conversation_id, session_factory)
        async with session_factory() as session:
            user_msg = Message(
                conversation_id=conversation_id,
                role="user",
                content=input.user_message,
                message_index=msg_count,
            )
            session.add(user_msg)
            await session.commit()
            await session.refresh(user_msg)
            next_index = msg_count + 1
    else:
        next_index = await _count_messages(conversation_id, session_factory)

    # 3. Retrieve
    try:
        chunks = await _retrieve_chunks(
            input.user_message, top_k, embedding_provider, session_factory
        )
    except Exception as exc:
        yield ErrorEvent(message=f"Retrieval failed: {exc}")
        yield DoneEvent()
        return

    top_sim = chunks[0].score if chunks else 0.0
    window = chunks[:avg_window]
    avg_sim = sum(c.score for c in window) / len(window) if window else 0.0

    yield RetrievalEvent(chunks=chunks, top_similarity=top_sim, avg_similarity=avg_sim)

    # 4. Assess confidence
    assessment: ConfidenceAssessment = assess_confidence(
        chunks, min_top_similarity, min_avg_similarity, avg_window
    )
    yield ConfidenceEvent(
        sufficient=assessment.sufficient,
        reason=assessment.reason,
        top_similarity=assessment.top_similarity,
        avg_similarity=assessment.avg_similarity,
    )

    # 5. Low confidence path
    if not assessment.sufficient:
        response_text = build_low_confidence_response(assessment.reason)
        yield TokenEvent(text=response_text)

        async with session_factory() as session:
            asst_msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=response_text,
                message_index=next_index,
                low_confidence=True,
                retrieved_chunk_ids=[c.chunk_id for c in chunks],
            )
            session.add(asst_msg)
            await session.commit()
            await session.refresh(asst_msg)

        yield SourcesEvent(sources=[])
        yield MessagePersistedEvent(
            conversation_id=conversation_id,
            assistant_message_id=asst_msg.id,
        )
        yield DoneEvent()
        return

    # 6. Stream generation
    context_chunks = chunks[:max_context_chunks]
    context_block = build_context_block(context_chunks)
    system_prompt = f"{GROUNDED_SYSTEM_PROMPT}\n\n{context_block}"
    model = llm_provider.model_for_tier(input.model_tier)

    collected: list[str] = []
    try:
        async for token in llm_provider.stream(
            messages=[ChatMessage(role="user", content=input.user_message)],
            system_prompt=system_prompt,
            model=model,
            max_tokens=max_output_tokens,
        ):
            collected.append(token)
            yield TokenEvent(text=token)
    except Exception as exc:
        logger.error("LLM streaming failed conversation_id=%s: %s", conversation_id, exc)
        yield ErrorEvent(message=f"Generation failed: {exc}")
        yield DoneEvent()
        return

    # 7. Post-stream: parse citations, persist
    full_text = "".join(collected)
    cleaned_text, cited_ids = parse_cited_chunks(full_text)

    retrieved_ids = [c.chunk_id for c in context_chunks]
    final_cited_ids = cited_ids if cited_ids else retrieved_ids

    async with session_factory() as session:
        asst_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=cleaned_text,
            message_index=next_index,
            retrieved_chunk_ids=retrieved_ids,
            cited_chunk_ids=final_cited_ids,
            model_used=model or llm_provider.identifier,
        )
        session.add(asst_msg)

        # touch updated_at on conversation
        conv = await session.get(Conversation, conversation_id)
        if conv is not None:
            from datetime import UTC, datetime
            conv.updated_at = datetime.now(UTC)
            session.add(conv)

        await session.commit()
        await session.refresh(asst_msg)

    # 8. Title generation for new conversations (background)
    if is_new_conversation:
        asyncio.create_task(
            _save_title(conversation_id, input.user_message, llm_provider, session_factory)
        )

    # 9. Emit sources
    cited_set = set(final_cited_ids)
    sources = [
        SourceInfo(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            filename=c.filename,
            text_preview=c.text[:200],
            score=c.score,
        )
        for c in context_chunks
        if c.chunk_id in cited_set
    ]
    yield SourcesEvent(sources=sources)
    yield MessagePersistedEvent(
        conversation_id=conversation_id,
        assistant_message_id=asst_msg.id,
    )
    yield DoneEvent()
