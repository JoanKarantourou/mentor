"""Trigger condition logic for memory extraction suggestions."""
from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.providers.embeddings import EmbeddingProvider


class TriggerResult(NamedTuple):
    should_suggest: bool
    reason: str | None  # "long_conversation" | "topic_shift" | "session_break"
    preview_count: int


_DECISION_KEYWORDS = (
    "we decided", "we chose", "the value is", "depends on", "the threshold",
    "the path is", "configured", "is set to", "fails silently", "note that",
    "important:", "gotcha", "be careful", "we use", "we agreed", "should be",
)


def _count_decision_keywords(messages: list[dict]) -> int:
    count = 0
    for m in messages:
        if m["role"] == "user":
            continue
        text_lower = m["content"].lower()
        for kw in _DECISION_KEYWORDS:
            if kw in text_lower:
                count += 1
                break
    return count


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 1.0  # undefined → assume no topic shift
    return dot / (norm_a * norm_b)


def _average_vector(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    n = len(vectors[0])
    avg = [0.0] * n
    for v in vectors:
        for i, x in enumerate(v):
            avg[i] += x
    return [x / len(vectors) for x in avg]


async def check_memory_trigger(
    conversation_id,
    current_user_message: str,
    session_factory: Callable[[], AsyncSession],
    embedding_provider: EmbeddingProvider,
    min_messages: int = 12,
    topic_shift_threshold: float = 0.5,
    session_break_minutes: int = 30,
) -> TriggerResult:
    """Check whether memory extraction should be suggested for this conversation."""
    async with session_factory() as session:
        result = await session.execute(
            text("""
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id = :cid
                ORDER BY message_index
            """),
            {"cid": str(conversation_id)},
        )
        rows = result.all()

    if len(rows) < min_messages:
        return TriggerResult(should_suggest=False, reason=None, preview_count=0)

    messages = [
        {"role": r.role, "content": r.content, "created_at": r.created_at}
        for r in rows
    ]

    # Session break: > N minutes since the last stored message
    last_ts: datetime = messages[-1]["created_at"]
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=UTC)
    if (datetime.now(UTC) - last_ts) > timedelta(minutes=session_break_minutes):
        preview_count = _count_decision_keywords(messages)
        return TriggerResult(should_suggest=True, reason="session_break", preview_count=preview_count)

    # Topic shift: cosine distance between current message and average of first 3 user messages
    user_texts = [m["content"] for m in messages if m["role"] == "user"]
    if len(user_texts) >= 3:
        try:
            first_vecs = await embedding_provider.embed(user_texts[:3])
            current_vec = (await embedding_provider.embed([current_user_message]))[0]
            avg_vec = _average_vector(first_vecs)
            similarity = _cosine_similarity(avg_vec, current_vec)
            if (1.0 - similarity) > topic_shift_threshold:
                preview_count = _count_decision_keywords(messages)
                return TriggerResult(should_suggest=True, reason="topic_shift", preview_count=preview_count)
        except Exception:
            pass  # embedding failure → skip topic-shift check silently

    # Long-conversation milestone: every min_messages-th message
    if len(rows) % min_messages == 0:
        preview_count = _count_decision_keywords(messages)
        return TriggerResult(should_suggest=True, reason="long_conversation", preview_count=preview_count)

    return TriggerResult(should_suggest=False, reason=None, preview_count=0)
