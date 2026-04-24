"""Tests for the chat orchestrator. DB is real (test_engine); LLM and retrieval are mocked."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.chat.citations import parse_cited_chunks
from app.chat.confidence import RetrievedChunk, assess_confidence
from app.chat.orchestrator import (
    ChatTurnInput,
    ConfidenceEvent,
    DoneEvent,
    MessagePersistedEvent,
    RetrievalEvent,
    SourcesEvent,
    TokenEvent,
    run_chat_turn,
)
from app.db import make_session_factory
from app.models.conversation import Conversation
from app.models.message import Message
from app.providers.embeddings import StubEmbeddingProvider
from app.providers.llm import ChatMessage, GenerationResult, StubLLMProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _low_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id=str(uuid4()),
            document_id=str(uuid4()),
            filename="doc.md",
            chunk_index=0,
            text="unrelated content",
            score=0.05,
            token_count=10,
        )
    ]


def _high_chunks() -> list[RetrievedChunk]:
    cid = str(uuid4())
    return [
        RetrievedChunk(
            chunk_id=cid,
            document_id=str(uuid4()),
            filename="pipeline.py",
            chunk_index=0,
            text="class IngestionPipeline: ...",
            score=0.82,
            token_count=20,
        )
    ]


async def _collect(gen) -> list:
    events = []
    async for event in gen:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# confidence.py unit tests
# ---------------------------------------------------------------------------


def test_assess_confidence_empty():
    result = assess_confidence([], 0.25, 0.20, 5)
    assert not result.sufficient
    assert "no results" in result.reason


def test_assess_confidence_low_top():
    chunks = _low_chunks()
    result = assess_confidence(chunks, 0.25, 0.20, 5)
    assert not result.sufficient
    assert "top similarity" in result.reason


def test_assess_confidence_sufficient():
    chunks = _high_chunks()
    result = assess_confidence(chunks, 0.25, 0.20, 5)
    assert result.sufficient
    assert result.reason == "ok"


# ---------------------------------------------------------------------------
# citations.py unit tests
# ---------------------------------------------------------------------------


def test_parse_cited_chunks_well_formed():
    text = "Here is the answer.\n<cited_chunks>abc-123,def-456</cited_chunks>"
    cleaned, ids = parse_cited_chunks(text)
    assert "abc-123" in ids
    assert "def-456" in ids
    assert "<cited_chunks>" not in cleaned


def test_parse_cited_chunks_malformed():
    text = "No tag here."
    cleaned, ids = parse_cited_chunks(text)
    assert cleaned == text
    assert ids == []


def test_parse_cited_chunks_strips_whitespace():
    text = "Answer.\n<cited_chunks>  abc-123 , def-456  </cited_chunks>"
    _, ids = parse_cited_chunks(text)
    assert ids == ["abc-123", "def-456"]


# ---------------------------------------------------------------------------
# Orchestrator: low confidence path
# ---------------------------------------------------------------------------


async def test_low_confidence_no_llm_call(test_engine: AsyncEngine) -> None:
    sf = make_session_factory(test_engine)
    llm = StubLLMProvider()

    with patch("app.chat.orchestrator._retrieve_chunks", new=AsyncMock(return_value=_low_chunks())):
        events = await _collect(
            run_chat_turn(
                ChatTurnInput(user_message="capital of France?"),
                session_factory=sf,
                embedding_provider=StubEmbeddingProvider(),
                llm_provider=llm,
                min_top_similarity=0.25,
                min_avg_similarity=0.20,
            )
        )

    types = [type(e).__name__ for e in events]
    assert "RetrievalEvent" in types
    assert "ConfidenceEvent" in types
    assert "TokenEvent" in types
    assert "MessagePersistedEvent" in types
    assert "DoneEvent" in types

    conf = next(e for e in events if isinstance(e, ConfidenceEvent))
    assert not conf.sufficient

    tok = next(e for e in events if isinstance(e, TokenEvent))
    assert "don't have enough" in tok.text


# ---------------------------------------------------------------------------
# Orchestrator: happy path
# ---------------------------------------------------------------------------


async def test_happy_path_streams_and_persists(test_engine: AsyncEngine) -> None:
    sf = make_session_factory(test_engine)
    chunks = _high_chunks()
    cited_id = chunks[0].chunk_id

    async def fake_stream(*args, **kwargs):
        yield f"The pipeline does X. <cited_chunks>{cited_id}</cited_chunks>"

    llm = StubLLMProvider()
    llm.stream = fake_stream

    with patch("app.chat.orchestrator._retrieve_chunks", new=AsyncMock(return_value=chunks)):
        events = await _collect(
            run_chat_turn(
                ChatTurnInput(user_message="how does ingestion work?"),
                session_factory=sf,
                embedding_provider=StubEmbeddingProvider(),
                llm_provider=llm,
                min_top_similarity=0.25,
                min_avg_similarity=0.20,
            )
        )

    conf = next(e for e in events if isinstance(e, ConfidenceEvent))
    assert conf.sufficient

    tokens = [e for e in events if isinstance(e, TokenEvent)]
    assert len(tokens) >= 1

    sources = next(e for e in events if isinstance(e, SourcesEvent))
    assert any(s.chunk_id == cited_id for s in sources.sources)

    persisted = next(e for e in events if isinstance(e, MessagePersistedEvent))
    assert persisted.conversation_id is not None

    # Verify DB state
    async with AsyncSession(test_engine) as session:
        conv = await session.get(Conversation, persisted.conversation_id)
        assert conv is not None
        msgs = (
            await session.exec(
                select(Message).where(Message.conversation_id == conv.id).order_by(Message.message_index)
            )
        ).all()
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"
        assert cited_id in (msgs[1].cited_chunk_ids or [])


# ---------------------------------------------------------------------------
# Orchestrator: conversation reuse
# ---------------------------------------------------------------------------


async def test_existing_conversation_reused(test_engine: AsyncEngine) -> None:
    sf = make_session_factory(test_engine)

    # Create conversation first
    async with AsyncSession(test_engine) as session:
        conv = Conversation(user_id="dev")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        conversation_id = conv.id

    with patch("app.chat.orchestrator._retrieve_chunks", new=AsyncMock(return_value=_low_chunks())):
        events = await _collect(
            run_chat_turn(
                ChatTurnInput(user_message="hello", conversation_id=conversation_id),
                session_factory=sf,
                embedding_provider=StubEmbeddingProvider(),
                llm_provider=StubLLMProvider(),
            )
        )

    persisted = next(e for e in events if isinstance(e, MessagePersistedEvent))
    assert persisted.conversation_id == conversation_id

    # Verify only one conversation exists
    async with AsyncSession(test_engine) as session:
        convs = (await session.exec(select(Conversation))).all()
    assert len(convs) == 1
