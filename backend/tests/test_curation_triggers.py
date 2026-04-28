"""Tests for curation trigger logic."""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.curation.triggers import (
    TriggerResult,
    _count_decision_keywords,
    _cosine_similarity,
    check_memory_trigger,
)
from app.db import make_session_factory
from app.models.conversation import Conversation
from app.models.message import Message
from app.providers.embeddings import StubEmbeddingProvider


# ---------------------------------------------------------------------------
# Controlled embedder that returns the same unit vector for all inputs
# (cosine similarity = 1.0 → no topic shift)
# ---------------------------------------------------------------------------

class _IdenticalEmbedder(StubEmbeddingProvider):
    """Returns the same unit vector for every text — guarantees no topic shift."""
    async def embed(self, texts: list[str]) -> list[list[float]]:
        dim = 1536
        v = [1.0 / math.sqrt(dim)] * dim
        return [v for _ in texts]


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


def test_cosine_similarity_identical():
    v = [1.0, 0.0, 0.5]
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(_cosine_similarity(a, b)) < 1e-6


def test_cosine_similarity_zero_norm_returns_one():
    a = [0.0, 0.0]
    b = [0.0, 0.0]
    assert _cosine_similarity(a, b) == 1.0


def test_count_decision_keywords_matches():
    msgs = [
        {"role": "user", "content": "what should we do?"},
        {"role": "assistant", "content": "We decided to use Redis for caching."},
        {"role": "user", "content": "ok"},
        {"role": "assistant", "content": "The threshold is set to 0.25 for confidence."},
    ]
    count = _count_decision_keywords(msgs)
    assert count == 2


def test_count_decision_keywords_only_assistant_messages():
    msgs = [
        {"role": "user", "content": "we decided nothing"},
        {"role": "assistant", "content": "no keywords here"},
    ]
    count = _count_decision_keywords(msgs)
    assert count == 0


# ---------------------------------------------------------------------------
# Integration tests with a real DB
# ---------------------------------------------------------------------------


async def _seed_conversation(session: AsyncSession, msg_count: int, age_minutes: int = 0) -> UUID:
    conv = Conversation(user_id="dev")
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    conv_id = conv.id  # capture before second commit

    base_time = datetime.now(UTC) - timedelta(minutes=age_minutes)
    for i in range(msg_count):
        role = "user" if i % 2 == 0 else "assistant"
        session.add(Message(
            conversation_id=conv_id,
            role=role,
            content=f"message {i}",
            message_index=i,
            created_at=base_time + timedelta(seconds=i),
        ))
    await session.commit()
    return conv_id


async def test_trigger_not_fired_below_min_messages(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    async with AsyncSession(test_engine) as session:
        conv_id = await _seed_conversation(session, msg_count=6)

    result = await check_memory_trigger(
        conversation_id=conv_id,
        current_user_message="hello",
        session_factory=sf,
        embedding_provider=_IdenticalEmbedder(),
        min_messages=12,
    )
    assert not result.should_suggest
    assert result.reason is None


async def test_trigger_session_break(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    async with AsyncSession(test_engine) as session:
        conv_id = await _seed_conversation(session, msg_count=12, age_minutes=60)

    result = await check_memory_trigger(
        conversation_id=conv_id,
        current_user_message="new topic",
        session_factory=sf,
        embedding_provider=_IdenticalEmbedder(),
        min_messages=12,
        session_break_minutes=30,
    )
    assert result.should_suggest
    assert result.reason == "session_break"


async def test_trigger_long_conversation_milestone(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    async with AsyncSession(test_engine) as session:
        conv_id = await _seed_conversation(session, msg_count=12, age_minutes=0)

    result = await check_memory_trigger(
        conversation_id=conv_id,
        current_user_message="continuing",
        session_factory=sf,
        embedding_provider=_IdenticalEmbedder(),  # no topic shift
        min_messages=12,
        session_break_minutes=30,
    )
    assert result.should_suggest
    assert result.reason == "long_conversation"


async def test_trigger_no_fire_between_milestones(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    async with AsyncSession(test_engine) as session:
        conv_id = await _seed_conversation(session, msg_count=15, age_minutes=0)

    result = await check_memory_trigger(
        conversation_id=conv_id,
        current_user_message="continuing",
        session_factory=sf,
        embedding_provider=_IdenticalEmbedder(),  # no topic shift
        min_messages=12,
        session_break_minutes=30,
    )
    # 15 % 12 = 3 ≠ 0 → milestone doesn't fire; no session break; no topic shift
    assert not result.should_suggest


async def test_trigger_topic_shift(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    async with AsyncSession(test_engine) as session:
        conv_id = await _seed_conversation(session, msg_count=12, age_minutes=0)

    # Orthogonal vectors → cosine similarity 0.0 → distance 1.0 > threshold 0.5
    async def orthogonal_embed(texts: list[str]) -> list[list[float]]:
        dim = 1536
        if len(texts) == 3:
            # first 3 user messages → [1, 0, 0, ...]
            return [[1.0] + [0.0] * (dim - 1) for _ in texts]
        # current message → [0, 1, 0, ...]
        return [[0.0, 1.0] + [0.0] * (dim - 2)]

    embedder = _IdenticalEmbedder()
    embedder.embed = orthogonal_embed  # type: ignore[method-assign]

    result = await check_memory_trigger(
        conversation_id=conv_id,
        current_user_message="completely unrelated topic",
        session_factory=sf,
        embedding_provider=embedder,
        min_messages=12,
        topic_shift_threshold=0.5,
        session_break_minutes=30,
    )
    assert result.should_suggest
    assert result.reason == "topic_shift"


async def test_trigger_embedding_failure_is_non_fatal(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    async with AsyncSession(test_engine) as session:
        conv_id = await _seed_conversation(session, msg_count=13, age_minutes=0)

    async def bad_embed(texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embed failed")

    embedder = _IdenticalEmbedder()
    embedder.embed = bad_embed  # type: ignore[method-assign]

    # Should not raise; topic-shift check silently skipped
    # 13 % 12 = 1 ≠ 0, no session break → should_suggest=False
    result = await check_memory_trigger(
        conversation_id=conv_id,
        current_user_message="test",
        session_factory=sf,
        embedding_provider=embedder,
        min_messages=12,
    )
    assert isinstance(result, TriggerResult)
    assert not result.should_suggest
