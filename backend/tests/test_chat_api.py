"""Tests for the chat API endpoints. Uses mocked orchestrator components."""

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.chat.confidence import RetrievedChunk
from app.models.conversation import Conversation
from app.models.message import Message


# ---------------------------------------------------------------------------
# SSE parsing helper
# ---------------------------------------------------------------------------


def parse_sse(body: str) -> list[tuple[str, str]]:
    """Return list of (event_type, data_string) from an SSE response body."""
    events = []
    current_event = "message"
    for line in body.splitlines():
        if line.startswith("event:"):
            current_event = line[6:].strip()
        elif line.startswith("data:"):
            events.append((current_event, line[5:].strip()))
        elif line == "":
            current_event = "message"
    return events


def _low_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=str(uuid4()),
        document_id=str(uuid4()),
        filename="doc.md",
        chunk_index=0,
        text="unrelated",
        score=0.05,
        token_count=5,
    )


def _high_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=str(uuid4()),
        document_id=str(uuid4()),
        filename="pipeline.py",
        chunk_index=0,
        text="class IngestionPipeline:",
        score=0.85,
        token_count=10,
    )


# ---------------------------------------------------------------------------
# POST /chat — low confidence (no corpus match)
# ---------------------------------------------------------------------------


async def test_chat_low_confidence_response(async_client) -> None:
    with patch(
        "app.chat.orchestrator._retrieve_chunks",
        new=AsyncMock(return_value=[_low_chunk()]),
    ):
        resp = await async_client.post("/chat", json={"message": "capital of France?"})

    assert resp.status_code == 200
    events = parse_sse(resp.text)
    event_types = [e for e, _ in events]
    assert "retrieval" in event_types
    assert "confidence" in event_types
    assert "token" in event_types
    assert "done" in event_types

    conf_data = json.loads(next(d for e, d in events if e == "confidence"))
    assert not conf_data["sufficient"]

    token_data = json.loads(next(d for e, d in events if e == "token"))
    assert "don't have enough" in token_data


# ---------------------------------------------------------------------------
# POST /chat — happy path (sufficient confidence)
# ---------------------------------------------------------------------------


async def test_chat_happy_path_events(async_client) -> None:
    chunk = _high_chunk()

    async def fake_stream(*args, **kwargs):
        yield f"The ingestion pipeline works like this. <cited_chunks>{chunk.chunk_id}</cited_chunks>"

    with (
        patch(
            "app.chat.orchestrator._retrieve_chunks",
            new=AsyncMock(return_value=[chunk]),
        ),
        patch("app.providers.llm.StubLLMProvider.stream", new=fake_stream),
    ):
        resp = await async_client.post("/chat", json={"message": "how does ingestion work?"})

    assert resp.status_code == 200
    events = parse_sse(resp.text)
    event_types = [e for e, _ in events]

    assert "retrieval" in event_types
    assert "confidence" in event_types
    assert "token" in event_types
    assert "sources" in event_types
    assert "message_persisted" in event_types
    assert "done" in event_types

    conf_data = json.loads(next(d for e, d in events if e == "confidence"))
    assert conf_data["sufficient"]

    persisted = json.loads(next(d for e, d in events if e == "message_persisted"))
    assert "conversation_id" in persisted
    assert "assistant_message_id" in persisted


# ---------------------------------------------------------------------------
# POST /chat — new conversation is created
# ---------------------------------------------------------------------------


async def test_chat_creates_conversation(async_client, test_engine: AsyncEngine) -> None:
    with patch(
        "app.chat.orchestrator._retrieve_chunks",
        new=AsyncMock(return_value=[_low_chunk()]),
    ):
        resp = await async_client.post("/chat", json={"message": "hello"})

    assert resp.status_code == 200
    events = parse_sse(resp.text)
    persisted = json.loads(next(d for e, d in events if e == "message_persisted"))
    conv_id = persisted["conversation_id"]

    async with AsyncSession(test_engine) as session:
        conv = await session.get(Conversation, conv_id)
    assert conv is not None


# ---------------------------------------------------------------------------
# GET /conversations
# ---------------------------------------------------------------------------


async def test_list_conversations(async_client, test_engine: AsyncEngine) -> None:
    # Seed a conversation with messages
    async with AsyncSession(test_engine) as session:
        conv = Conversation(user_id="dev", title="Test conv")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        session.add(Message(
            conversation_id=conv.id,
            role="user",
            content="hello",
            message_index=0,
        ))
        await session.commit()

    resp = await async_client.get("/conversations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Test conv"
    assert data[0]["message_count"] == 1


# ---------------------------------------------------------------------------
# GET /conversations/{id}
# ---------------------------------------------------------------------------


async def test_get_conversation(async_client, test_engine: AsyncEngine) -> None:
    async with AsyncSession(test_engine) as session:
        conv = Conversation(user_id="dev", title="Detail test")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        cid = conv.id  # capture before second commit expires the instance
        session.add(Message(
            conversation_id=cid,
            role="user",
            content="question",
            message_index=0,
        ))
        session.add(Message(
            conversation_id=cid,
            role="assistant",
            content="answer",
            message_index=1,
        ))
        await session.commit()

    resp = await async_client.get(f"/conversations/{cid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Detail test"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"


# ---------------------------------------------------------------------------
# DELETE /conversations/{id}
# ---------------------------------------------------------------------------


async def test_delete_conversation(async_client, test_engine: AsyncEngine) -> None:
    async with AsyncSession(test_engine) as session:
        conv = Conversation(user_id="dev")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        cid = conv.id  # capture before second commit expires the instance
        session.add(Message(
            conversation_id=cid,
            role="user",
            content="to be deleted",
            message_index=0,
        ))
        await session.commit()

    resp = await async_client.delete(f"/conversations/{cid}")
    assert resp.status_code == 204

    # Conversation and messages are gone
    async with AsyncSession(test_engine) as session:
        assert await session.get(Conversation, cid) is None
        msgs = (
            await session.exec(select(Message).where(Message.conversation_id == cid))
        ).all()
        assert len(msgs) == 0


# ---------------------------------------------------------------------------
# GET /conversations/{id} — 404 for missing
# ---------------------------------------------------------------------------


async def test_get_conversation_404(async_client) -> None:
    resp = await async_client.get(f"/conversations/{uuid4()}")
    assert resp.status_code == 404
