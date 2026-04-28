"""E2E: Chat flows — grounded answers, honesty, web search, conversation continuity."""

import asyncio
import json
from typing import AsyncIterator

import httpx
import pytest


async def collect_sse(response: httpx.Response) -> list[dict]:
    """Parse SSE stream into list of {event, data} dicts."""
    events = []
    current_event = "message"
    async for line in response.aiter_lines():
        if line.startswith("event:"):
            current_event = line[6:].strip()
        elif line.startswith("data:"):
            raw = line[5:].strip()
            if raw:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = raw
            else:
                data = None
            events.append({"event": current_event, "data": data})
        elif line == "":
            current_event = "message"
    return events


async def send_chat(
    client: httpx.AsyncClient,
    message: str,
    conversation_id: str | None = None,
    enable_web_search: bool = False,
) -> list[dict]:
    body = {
        "message": message,
        "conversation_id": conversation_id,
        "model_tier": "default",
        "enable_web_search": enable_web_search,
    }
    async with client.stream("POST", "/chat", json=body) as resp:
        resp.raise_for_status()
        return await collect_sse(resp)


def get_event(events: list[dict], event_type: str) -> dict | None:
    return next((e for e in events if e["event"] == event_type), None)


def get_all_events(events: list[dict], event_type: str) -> list[dict]:
    return [e for e in events if e["event"] == event_type]


# ---------------------------------------------------------------------------
# Scenario 1: Grounded answer about indexed documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grounded_answer_cites_document():
    """A question about indexed content should produce a confident answer with sources."""
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=60.0) as client:
        events = await send_chat(client, "What stages does the ingestion pipeline have?")

    confidence = get_event(events, "confidence")
    assert confidence is not None

    token_events = get_all_events(events, "token")
    full_answer = "".join(e["data"] for e in token_events if e["data"])

    sources = get_event(events, "sources")
    assert sources is not None

    # Verify done
    assert get_event(events, "done") is not None


# ---------------------------------------------------------------------------
# Scenario 2: Honesty — off-topic questions must hit low-confidence path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_off_topic_questions_are_honest():
    """Questions clearly not in the corpus must produce low-confidence responses."""
    off_topic = [
        "What is the capital of France?",
        "How do I bake a chocolate cake?",
        "What is the weather like in Tokyo?",
        "Who won the 2024 Olympics in swimming?",
        "What is the GDP of Germany?",
    ]
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=120.0) as client:
        for question in off_topic:
            events = await send_chat(client, question)
            confidence = get_event(events, "confidence")
            assert confidence is not None, f"No confidence event for: {question}"
            # Should be low confidence for off-topic questions
            assert not confidence["data"]["sufficient"], (
                f"Expected low confidence for off-topic: {question!r}"
            )


# ---------------------------------------------------------------------------
# Scenario 3: Web search opt-in
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_web_search_opt_in_events():
    """With enable_web_search=True and stub provider, web events appear in stream."""
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=60.0) as client:
        events = await send_chat(
            client,
            "Explain the ingestion pipeline",
            enable_web_search=True,
        )

    assert get_event(events, "web_search_started") is not None
    assert get_event(events, "web_search_results") is not None

    web_results = get_event(events, "web_search_results")
    assert isinstance(web_results["data"], list)
    assert len(web_results["data"]) > 0


@pytest.mark.asyncio
async def test_web_search_message_persisted_with_flag():
    """Messages with web search should have web_search_used=true in the conversation."""
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=60.0) as client:
        events = await send_chat(client, "test web search flag", enable_web_search=True)

        persisted = get_event(events, "message_persisted")
        assert persisted is not None
        conv_id = persisted["data"]["conversation_id"]

        conv = await client.get(f"/conversations/{conv_id}")
        assert conv.status_code == 200

        messages = conv.json()["messages"]
        asst_messages = [m for m in messages if m["role"] == "assistant"]
        assert len(asst_messages) == 1
        assert asst_messages[0]["web_search_used"] is True


# ---------------------------------------------------------------------------
# Scenario 4: Conversation continuity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conversation_continuity():
    """Multi-turn conversation retains all messages."""
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=120.0) as client:
        conv_id = None
        for i in range(3):
            events = await send_chat(client, f"Question {i}", conversation_id=conv_id)
            persisted = get_event(events, "message_persisted")
            assert persisted is not None
            conv_id = persisted["data"]["conversation_id"]

        conv = await client.get(f"/conversations/{conv_id}")
        assert conv.status_code == 200
        messages = conv.json()["messages"]
        user_msgs = [m for m in messages if m["role"] == "user"]
        asst_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(user_msgs) == 3
        assert len(asst_msgs) == 3

        # Delete and verify 404
        del_resp = await client.delete(f"/conversations/{conv_id}")
        assert del_resp.status_code == 204

        get_resp = await client.get(f"/conversations/{conv_id}")
        assert get_resp.status_code == 404
