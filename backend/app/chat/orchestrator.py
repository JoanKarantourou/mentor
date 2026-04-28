from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.chat.citations import parse_citations
from app.chat.confidence import ConfidenceAssessment, RetrievedChunk, assess_confidence
from app.chat.prompts import (
    GROUNDED_SYSTEM_PROMPT,
    GROUNDED_SYSTEM_PROMPT_WITH_WEB,
    build_combined_context,
    build_context_block,
    build_low_confidence_response,
)
from app.chat.title import generate_title
from app.models.conversation import Conversation
from app.models.message import Message
from app.providers.embeddings import EmbeddingProvider
from app.providers.llm import ChatMessage, LLMProvider
from app.providers.web_search import WebSearchProvider, WebSearchResult

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
class WebSearchStartedEvent:
    pass


@dataclass
class WebSearchResultsEvent:
    results: list[WebSearchResult]


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
class WebSourceInfo:
    rank: int
    title: str
    url: str
    snippet: str
    published_date: str | None
    source_domain: str


@dataclass
class SourcesEvent:
    sources: list[SourceInfo]
    web_sources: list[WebSourceInfo] = field(default_factory=list)


@dataclass
class MessagePersistedEvent:
    conversation_id: UUID
    assistant_message_id: UUID


@dataclass
class ErrorEvent:
    message: str


@dataclass
class GapAnalysisEvent:
    missing_topic: str
    related_topics_present: list[str]
    suggested_document_types: list[str]
    related_document_ids: list[str]  # UUIDs as strings


@dataclass
class MemorySuggestionEvent:
    should_suggest: bool
    reason: str  # "long_conversation" | "topic_shift" | "session_break"
    preview_count: int


@dataclass
class DoneEvent:
    pass


ChatEvent = (
    RetrievalEvent
    | ConfidenceEvent
    | WebSearchStartedEvent
    | WebSearchResultsEvent
    | TokenEvent
    | SourcesEvent
    | MessagePersistedEvent
    | GapAnalysisEvent
    | MemorySuggestionEvent
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
    enable_web_search: bool = False
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
    web_search_provider: WebSearchProvider | None = None,
    top_k: int = 8,
    min_top_similarity: float = 0.25,
    min_avg_similarity: float = 0.20,
    avg_window: int = 5,
    max_context_chunks: int = 8,
    max_output_tokens: int = 2048,
    web_search_max_results: int = 5,
    gap_analysis_enabled: bool = True,
    memory_extraction_min_messages: int = 12,
    memory_extraction_topic_shift_threshold: float = 0.5,
    memory_extraction_session_break_minutes: int = 30,
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
        try:
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
        except Exception as exc:
            yield ErrorEvent(message=f"Failed to persist user message: {exc}")
            yield DoneEvent()
            return
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

    # 5. Optionally run web search (regardless of corpus confidence)
    web_results: list[WebSearchResult] = []
    if input.enable_web_search and web_search_provider is not None:
        yield WebSearchStartedEvent()
        try:
            web_results = await web_search_provider.search(
                input.user_message, max_results=web_search_max_results
            )
        except Exception as exc:
            logger.warning("Web search failed, continuing without it: %s", exc)
            web_results = []
        yield WebSearchResultsEvent(results=web_results)

    # 6. Low confidence path (only when web search is not providing fallback)
    if not assessment.sufficient and not web_results:
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

        # Gap analysis — run after persisting so the user sees the refusal text quickly
        if gap_analysis_enabled:
            try:
                from app.curation.gap_analyzer import analyze_gap
                gap = await analyze_gap(
                    user_query=input.user_message,
                    retrieved_chunks=chunks,
                    session_factory=session_factory,
                    llm_provider=llm_provider,
                )
                if gap is not None:
                    yield GapAnalysisEvent(
                        missing_topic=gap.missing_topic,
                        related_topics_present=gap.related_topics_present,
                        suggested_document_types=gap.suggested_document_types,
                        related_document_ids=[str(d) for d in gap.related_document_ids],
                    )
            except Exception as exc:
                logger.warning("gap analysis error (non-fatal): %s", exc)

        # Emit closest chunks as sources even on low-confidence path
        low_conf_sources = [
            SourceInfo(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                filename=c.filename,
                text_preview=c.text[:200],
                score=c.score,
            )
            for c in chunks[:3]
        ]
        yield SourcesEvent(sources=low_conf_sources)
        yield MessagePersistedEvent(
            conversation_id=conversation_id,
            assistant_message_id=asst_msg.id,
        )
        yield DoneEvent()
        return

    # 7. Build context (corpus only, web only, or combined)
    context_chunks = chunks[:max_context_chunks] if assessment.sufficient else []
    if web_results:
        context_block = build_combined_context(context_chunks, web_results)
        system_prompt = f"{GROUNDED_SYSTEM_PROMPT_WITH_WEB}\n\n{context_block}"
    else:
        context_block = build_context_block(context_chunks)
        system_prompt = f"{GROUNDED_SYSTEM_PROMPT}\n\n{context_block}"

    model = llm_provider.model_for_tier(input.model_tier)

    # 8. Stream generation
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

    # 9. Post-stream: parse citations, persist
    full_text = "".join(collected)
    cleaned_text, cited_ids, cited_web_indices = parse_citations(full_text)

    retrieved_ids = [c.chunk_id for c in context_chunks]
    final_cited_ids = cited_ids if cited_ids else retrieved_ids

    web_results_as_dicts = [
        {
            "title": r.title,
            "url": r.url,
            "snippet": r.snippet,
            "published_date": r.published_date,
            "source_domain": r.source_domain,
            "rank": r.rank,
        }
        for r in web_results
    ] if web_results else None

    async with session_factory() as session:
        asst_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=cleaned_text,
            message_index=next_index,
            retrieved_chunk_ids=retrieved_ids,
            cited_chunk_ids=final_cited_ids,
            model_used=model or llm_provider.identifier,
            web_search_used=bool(web_results),
            web_search_results=web_results_as_dicts,
            web_search_provider=web_search_provider.identifier if web_results and web_search_provider else None,
        )
        session.add(asst_msg)

        conv = await session.get(Conversation, conversation_id)
        if conv is not None:
            from datetime import UTC, datetime
            conv.updated_at = datetime.now(UTC)
            session.add(conv)

        await session.commit()
        await session.refresh(asst_msg)

    # 10. Title generation for new conversations (background)
    if is_new_conversation:
        asyncio.create_task(
            _save_title(conversation_id, input.user_message, llm_provider, session_factory)
        )

    # 11. Emit sources
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

    cited_web_set = set(cited_web_indices)
    web_sources = [
        WebSourceInfo(
            rank=r.rank,
            title=r.title,
            url=r.url,
            snippet=r.snippet,
            published_date=r.published_date,
            source_domain=r.source_domain,
        )
        for r in web_results
        if (r.rank + 1) in cited_web_set or not cited_web_indices
    ]

    yield SourcesEvent(sources=sources, web_sources=web_sources)
    yield MessagePersistedEvent(
        conversation_id=conversation_id,
        assistant_message_id=asst_msg.id,
    )

    # Memory suggestion — check after message is persisted
    try:
        from app.curation.triggers import check_memory_trigger
        trigger = await check_memory_trigger(
            conversation_id=conversation_id,
            current_user_message=input.user_message,
            session_factory=session_factory,
            embedding_provider=embedding_provider,
            min_messages=memory_extraction_min_messages,
            topic_shift_threshold=memory_extraction_topic_shift_threshold,
            session_break_minutes=memory_extraction_session_break_minutes,
        )
        if trigger.should_suggest:
            yield MemorySuggestionEvent(
                should_suggest=True,
                reason=trigger.reason or "long_conversation",
                preview_count=trigger.preview_count,
            )
    except Exception as exc:
        logger.warning("memory trigger check error (non-fatal): %s", exc)

    yield DoneEvent()
