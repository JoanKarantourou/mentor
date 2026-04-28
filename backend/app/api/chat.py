import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.chat.orchestrator import (
    ChatTurnInput,
    ConfidenceEvent,
    DoneEvent,
    ErrorEvent,
    GapAnalysisEvent,
    MemorySuggestionEvent,
    MessagePersistedEvent,
    RetrievalEvent,
    SourcesEvent,
    TokenEvent,
    WebSearchResultsEvent,
    WebSearchStartedEvent,
    run_chat_turn,
)
from app.db import get_session
from app.models.conversation import Conversation
from app.models.message import Message

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    conversation_id: UUID | None = None
    model_tier: str = "default"
    enable_web_search: bool = False


class ConversationListItem(BaseModel):
    id: UUID
    title: str | None
    created_at: str
    updated_at: str
    message_count: int

    model_config = {"from_attributes": True}


class MessageRead(BaseModel):
    id: UUID
    role: str
    content: str
    message_index: int
    retrieved_chunk_ids: list | None
    cited_chunk_ids: list | None
    model_used: str | None
    input_tokens: int | None
    output_tokens: int | None
    low_confidence: bool
    web_search_used: bool
    created_at: str

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: UUID
    title: str | None
    user_id: str
    created_at: str
    updated_at: str
    messages: list[MessageRead]


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


# ---------------------------------------------------------------------------
# Shared event serializer
# ---------------------------------------------------------------------------


def _serialize_event(event) -> str | None:
    if isinstance(event, RetrievalEvent):
        return _sse("retrieval", json.dumps({
            "chunk_ids": [c.chunk_id for c in event.chunks],
            "top_similarity": event.top_similarity,
            "avg_similarity": event.avg_similarity,
        }))
    elif isinstance(event, ConfidenceEvent):
        return _sse("confidence", json.dumps({
            "sufficient": event.sufficient,
            "reason": event.reason,
        }))
    elif isinstance(event, WebSearchStartedEvent):
        return _sse("web_search_started", json.dumps({}))
    elif isinstance(event, WebSearchResultsEvent):
        return _sse("web_search_results", json.dumps([
            {
                "rank": r.rank,
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "published_date": r.published_date,
                "source_domain": r.source_domain,
            }
            for r in event.results
        ]))
    elif isinstance(event, TokenEvent):
        return _sse("token", json.dumps(event.text))
    elif isinstance(event, SourcesEvent):
        return _sse("sources", json.dumps({
            "sources": [
                {
                    "chunk_id": s.chunk_id,
                    "document_id": s.document_id,
                    "filename": s.filename,
                    "text_preview": s.text_preview,
                    "score": s.score,
                }
                for s in event.sources
            ],
            "web_sources": [
                {
                    "rank": w.rank,
                    "title": w.title,
                    "url": w.url,
                    "snippet": w.snippet,
                    "published_date": w.published_date,
                    "source_domain": w.source_domain,
                }
                for w in event.web_sources
            ],
        }))
    elif isinstance(event, MessagePersistedEvent):
        return _sse("message_persisted", json.dumps({
            "conversation_id": str(event.conversation_id),
            "assistant_message_id": str(event.assistant_message_id),
        }))
    elif isinstance(event, ErrorEvent):
        return _sse("error", json.dumps({"message": event.message}))
    elif isinstance(event, GapAnalysisEvent):
        return _sse("gap_analysis", json.dumps({
            "missing_topic": event.missing_topic,
            "related_topics_present": event.related_topics_present,
            "suggested_document_types": event.suggested_document_types,
            "related_document_ids": event.related_document_ids,
        }))
    elif isinstance(event, MemorySuggestionEvent):
        return _sse("memory_suggestion", json.dumps({
            "should_suggest": event.should_suggest,
            "reason": event.reason,
            "preview_count": event.preview_count,
        }))
    elif isinstance(event, DoneEvent):
        return _sse("done", "")
    return None


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------


@router.post("/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    embedding_provider = request.app.state.embedding_provider
    llm_provider = request.app.state.llm_provider
    web_search_provider = request.app.state.web_search_provider
    session_factory = request.app.state.session_factory
    cfg = request.app.state.chat_config

    turn_input = ChatTurnInput(
        user_message=body.message,
        conversation_id=body.conversation_id,
        model_tier=body.model_tier,
        enable_web_search=body.enable_web_search,
    )

    async def event_gen():
        try:
            async for event in run_chat_turn(
                turn_input,
                session_factory=session_factory,
                embedding_provider=embedding_provider,
                llm_provider=llm_provider,
                web_search_provider=web_search_provider,
                **cfg,
            ):
                serialized = _serialize_event(event)
                if serialized is not None:
                    yield serialized
        except Exception as exc:
            logger.exception("Unhandled error in chat stream")
            yield _sse("error", json.dumps({"message": str(exc)}))
            yield _sse("done", "")

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# POST /chat/{message_id}/regenerate
# ---------------------------------------------------------------------------


@router.post("/chat/{message_id}/regenerate")
async def regenerate(message_id: UUID, request: Request) -> StreamingResponse:
    session_factory = request.app.state.session_factory
    embedding_provider = request.app.state.embedding_provider
    llm_provider = request.app.state.llm_provider
    web_search_provider = request.app.state.web_search_provider
    cfg = request.app.state.chat_config

    async with session_factory() as session:
        asst_msg = await session.get(Message, message_id)
        if asst_msg is None or asst_msg.role != "assistant":
            raise HTTPException(status_code=404, detail="Assistant message not found")
        if asst_msg.message_index == 0:
            raise HTTPException(status_code=400, detail="No preceding user message")
        user_msg = (
            await session.exec(
                select(Message).where(
                    Message.conversation_id == asst_msg.conversation_id,
                    Message.message_index == asst_msg.message_index - 1,
                    Message.role == "user",
                )
            )
        ).first()
        if user_msg is None:
            raise HTTPException(status_code=404, detail="Preceding user message not found")
        conversation_id = asst_msg.conversation_id
        user_text = user_msg.content

    async with session_factory() as session:
        old = await session.get(Message, message_id)
        if old:
            await session.delete(old)
            await session.commit()

    turn_input = ChatTurnInput(
        user_message=user_text,
        conversation_id=conversation_id,
        model_tier="strong",
        _skip_user_persist=True,
    )

    async def event_gen():
        try:
            async for event in run_chat_turn(
                turn_input,
                session_factory=session_factory,
                embedding_provider=embedding_provider,
                llm_provider=llm_provider,
                web_search_provider=web_search_provider,
                **cfg,
            ):
                serialized = _serialize_event(event)
                if serialized is not None:
                    yield serialized
        except Exception as exc:
            logger.exception("Unhandled error in regenerate stream")
            yield _sse("error", json.dumps({"message": str(exc)}))
            yield _sse("done", "")

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# GET /conversations
# ---------------------------------------------------------------------------


@router.get("/conversations")
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[ConversationListItem]:
    stmt = (
        select(
            Conversation,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.deleted_at.is_(None))
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.exec(stmt)).all()
    return [
        ConversationListItem(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at.isoformat(),
            updated_at=conv.updated_at.isoformat(),
            message_count=count,
        )
        for conv, count in rows
    ]


# ---------------------------------------------------------------------------
# GET /conversations/{id}
# ---------------------------------------------------------------------------


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ConversationDetail:
    conv = await session.get(Conversation, conversation_id)
    if conv is None or conv.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = (
        await session.exec(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.message_index)
        )
    ).all()

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        user_id=conv.user_id,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        messages=[
            MessageRead(
                id=m.id,
                role=m.role,
                content=m.content,
                message_index=m.message_index,
                retrieved_chunk_ids=m.retrieved_chunk_ids,
                cited_chunk_ids=m.cited_chunk_ids,
                model_used=m.model_used,
                input_tokens=m.input_tokens,
                output_tokens=m.output_tokens,
                low_confidence=m.low_confidence,
                web_search_used=m.web_search_used,
                created_at=m.created_at.isoformat(),
            )
            for m in msgs
        ],
    )


# ---------------------------------------------------------------------------
# DELETE /conversations/{id}
# ---------------------------------------------------------------------------


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    conv = await session.get(Conversation, conversation_id)
    if conv is None or conv.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await session.delete(conv)
    await session.commit()
