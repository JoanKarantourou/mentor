"""Chat API edge cases: missing conversations, web search SSE events, regenerate edge cases."""

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.chat.confidence import RetrievedChunk
from app.models.conversation import Conversation
from app.models.message import Message


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


def parse_sse(body: str) -> list[tuple[str, str]]:
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


# ---------------------------------------------------------------------------
# Non-existent conversation → 404
# ---------------------------------------------------------------------------


async def test_get_nonexistent_conversation_returns_404(async_client: AsyncClient) -> None:
    resp = await async_client.get(f"/conversations/{uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Web search SSE events appear in stream
# ---------------------------------------------------------------------------


async def test_chat_with_web_search_emits_web_events(async_client: AsyncClient) -> None:
    chunk = _high_chunk()

    async def fake_stream(*args, **kwargs):
        yield f"Answer with web. <cited_web>1</cited_web>"

    with (
        patch(
            "app.chat.orchestrator._retrieve_chunks",
            new=AsyncMock(return_value=[chunk]),
        ),
        patch("app.providers.llm.StubLLMProvider.stream", new=fake_stream),
    ):
        resp = await async_client.post(
            "/chat",
            json={"message": "what is RAG?", "enable_web_search": True},
        )

    assert resp.status_code == 200
    events = parse_sse(resp.text)
    event_types = [e for e, _ in events]
    assert "web_search_started" in event_types
    assert "web_search_results" in event_types

    # web_search_results should contain a list
    web_results_data = json.loads(next(d for e, d in events if e == "web_search_results"))
    assert isinstance(web_results_data, list)
    assert len(web_results_data) > 0


async def test_chat_without_web_search_no_web_events(async_client: AsyncClient) -> None:
    with patch(
        "app.chat.orchestrator._retrieve_chunks",
        new=AsyncMock(return_value=[_low_chunk()]),
    ):
        resp = await async_client.post(
            "/chat",
            json={"message": "capital of France?", "enable_web_search": False},
        )

    event_types = [e for e, _ in parse_sse(resp.text)]
    assert "web_search_started" not in event_types
    assert "web_search_results" not in event_types


# ---------------------------------------------------------------------------
# Sources event includes web_sources field
# ---------------------------------------------------------------------------


async def test_sources_event_includes_web_sources_field(async_client: AsyncClient) -> None:
    chunk = _high_chunk()

    async def fake_stream(*args, **kwargs):
        yield f"Answer. <cited_web>1</cited_web>"

    with (
        patch(
            "app.chat.orchestrator._retrieve_chunks",
            new=AsyncMock(return_value=[chunk]),
        ),
        patch("app.providers.llm.StubLLMProvider.stream", new=fake_stream),
    ):
        resp = await async_client.post(
            "/chat",
            json={"message": "test", "enable_web_search": True},
        )

    events = parse_sse(resp.text)
    sources_data = json.loads(next(d for e, d in events if e == "sources"))
    assert "sources" in sources_data
    assert "web_sources" in sources_data


# ---------------------------------------------------------------------------
# Conversation continuity (send 3 messages, fetch all)
# ---------------------------------------------------------------------------


async def test_conversation_continuity(
    async_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    # Create conversation with 3 exchanges
    conv_id = None
    for i in range(3):
        body = {"message": f"question {i}", "enable_web_search": False}
        if conv_id:
            body["conversation_id"] = conv_id

        with patch(
            "app.chat.orchestrator._retrieve_chunks",
            new=AsyncMock(return_value=[_low_chunk()]),
        ):
            resp = await async_client.post("/chat", json=body)

        assert resp.status_code == 200
        events = parse_sse(resp.text)
        persisted = json.loads(next(d for e, d in events if e == "message_persisted"))
        conv_id = persisted["conversation_id"]

    detail = await async_client.get(f"/conversations/{conv_id}")
    assert detail.status_code == 200
    data = detail.json()
    messages = data["messages"]
    user_msgs = [m for m in messages if m["role"] == "user"]
    asst_msgs = [m for m in messages if m["role"] == "assistant"]
    assert len(user_msgs) == 3
    assert len(asst_msgs) == 3


# ---------------------------------------------------------------------------
# Conversation delete → 404 on next fetch
# ---------------------------------------------------------------------------


async def test_conversation_delete_then_404(
    async_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    async with AsyncSession(test_engine) as session:
        conv = Conversation(user_id="dev", title="To delete")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        cid = conv.id

    del_resp = await async_client.delete(f"/conversations/{cid}")
    assert del_resp.status_code == 204

    get_resp = await async_client.get(f"/conversations/{cid}")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Regenerate: no preceding user message (edge case)
# ---------------------------------------------------------------------------


async def test_regenerate_no_preceding_user_message(
    async_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    async with AsyncSession(test_engine) as session:
        conv = Conversation(user_id="dev")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)

        # Only an assistant message with index 0 — no user message before it
        asst = Message(
            conversation_id=conv.id,
            role="assistant",
            content="orphan answer",
            message_index=0,
        )
        session.add(asst)
        await session.commit()
        await session.refresh(asst)
        asst_id = asst.id

    resp = await async_client.post(f"/chat/{asst_id}/regenerate")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Regenerate: non-existent message → 404
# ---------------------------------------------------------------------------


async def test_regenerate_nonexistent_message_404(async_client: AsyncClient) -> None:
    resp = await async_client.post(f"/chat/{uuid4()}/regenerate")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# web_search_used persisted on message
# ---------------------------------------------------------------------------


async def test_message_web_search_used_field_persisted(
    async_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    chunk = _high_chunk()

    async def fake_stream(*args, **kwargs):
        yield "Answer. <cited_web>1</cited_web>"

    with (
        patch("app.chat.orchestrator._retrieve_chunks", new=AsyncMock(return_value=[chunk])),
        patch("app.providers.llm.StubLLMProvider.stream", new=fake_stream),
    ):
        resp = await async_client.post(
            "/chat",
            json={"message": "test web", "enable_web_search": True},
        )

    events = parse_sse(resp.text)
    persisted = json.loads(next(d for e, d in events if e == "message_persisted"))
    asst_id = persisted["assistant_message_id"]

    async with AsyncSession(test_engine) as session:
        msg = await session.get(Message, asst_id)
        assert msg is not None
        assert msg.web_search_used is True


async def test_message_web_search_used_false_without_search(
    async_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    chunk = _high_chunk()

    async def fake_stream(*args, **kwargs):
        yield f"Corpus answer. <cited_chunks>{chunk.chunk_id}</cited_chunks>"

    with (
        patch("app.chat.orchestrator._retrieve_chunks", new=AsyncMock(return_value=[chunk])),
        patch("app.providers.llm.StubLLMProvider.stream", new=fake_stream),
    ):
        resp = await async_client.post(
            "/chat",
            json={"message": "corpus only", "enable_web_search": False},
        )

    events = parse_sse(resp.text)
    persisted = json.loads(next(d for e, d in events if e == "message_persisted"))
    asst_id = persisted["assistant_message_id"]

    async with AsyncSession(test_engine) as session:
        msg = await session.get(Message, asst_id)
        assert msg is not None
        assert msg.web_search_used is False
