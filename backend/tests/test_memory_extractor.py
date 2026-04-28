"""Tests for memory extraction."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.curation.memory_extractor import ExtractedMemory, extract_memory
from app.db import make_session_factory
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.message import Message
from app.providers.llm import GenerationResult, StubLLMProvider


async def _make_conversation(session: AsyncSession, messages: list[tuple[str, str]]):
    conv = Conversation(user_id="dev")
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    conv_id = conv.id  # capture before second commit
    for i, (role, content) in enumerate(messages):
        msg = Message(
            conversation_id=conv_id,
            role=role,
            content=content,
            message_index=i,
        )
        session.add(msg)
    await session.commit()
    return conv_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_extract_memory_well_formed_json(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    async with AsyncSession(test_engine) as session:
        conv_id = await _make_conversation(session, [
            ("user", "What retry strategy did we choose?"),
            ("assistant", "We decided on exponential backoff with max 5 retries."),
            ("user", "And the base delay?"),
            ("assistant", "The base delay is set to 200ms."),
        ])

    llm = StubLLMProvider()
    payload = json.dumps({
        "title": "Retry strategy decisions",
        "facts": [
            {"content": "We chose exponential backoff with max 5 retries.", "source_message_indices": [1]},
            {"content": "The base delay is set to 200ms.", "source_message_indices": [3]},
        ],
    })
    llm.generate = lambda **kw: _make_result(payload)

    result = await extract_memory(conv_id, sf, llm)

    assert isinstance(result, ExtractedMemory)
    assert result.title == "Retry strategy decisions"
    assert result.fact_count == 2
    assert "exponential backoff" in result.content


async def test_extract_memory_malformed_json_uses_fallback(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    async with AsyncSession(test_engine) as session:
        conv_id = await _make_conversation(session, [
            ("user", "how does this work?"),
            ("assistant", "# Key notes\n- Module A depends on module B.\n- Threshold is 0.25."),
        ])

    call_count = 0

    async def fake_generate(messages, system_prompt, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return GenerationResult(text="not valid json {{{", input_tokens=0, output_tokens=0, model="stub", stop_reason="end_turn")
        return GenerationResult(text="# Key notes\n- Threshold is 0.25.", input_tokens=0, output_tokens=0, model="stub", stop_reason="end_turn")

    llm = StubLLMProvider()
    llm.generate = fake_generate

    result = await extract_memory(conv_id, sf, llm)
    assert call_count == 2  # primary + fallback
    assert isinstance(result, ExtractedMemory)
    assert result.fact_count == 0  # fallback doesn't parse facts


async def test_extract_memory_zero_facts(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    async with AsyncSession(test_engine) as session:
        conv_id = await _make_conversation(session, [
            ("user", "hi"),
            ("assistant", "Hello!"),
        ])

    llm = StubLLMProvider()
    payload = json.dumps({"title": "Small talk", "facts": []})
    llm.generate = lambda **kw: _make_result(payload)

    result = await extract_memory(conv_id, sf, llm)
    assert result.fact_count == 0
    assert "_No durable facts_" in result.content or "No durable facts" in result.content


async def test_extract_memory_empty_conversation(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    async with AsyncSession(test_engine) as session:
        conv = Conversation(user_id="dev")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        conv_id = conv.id

    llm = StubLLMProvider()
    result = await extract_memory(conv_id, sf, llm)
    assert "Empty conversation" in result.title or result.fact_count == 0


async def test_extract_memory_source_message_ids_populated(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    async with AsyncSession(test_engine) as session:
        conv_id = await _make_conversation(session, [
            ("user", "what port does the API run on?"),
            ("assistant", "The API runs on port 8000."),
            ("user", "thanks"),
            ("assistant", "No problem."),
        ])

    llm = StubLLMProvider()
    payload = json.dumps({
        "title": "API port configuration",
        "facts": [
            {"content": "The API runs on port 8000.", "source_message_indices": [1]},
        ],
    })
    llm.generate = lambda **kw: _make_result(payload)

    result = await extract_memory(conv_id, sf, llm)
    assert len(result.source_message_ids) >= 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_result(text: str):
    return GenerationResult(text=text, input_tokens=0, output_tokens=0, model="stub", stop_reason="end_turn")
