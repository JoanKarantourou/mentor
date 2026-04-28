"""Tests for gap analysis."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.chat.confidence import RetrievedChunk
from app.curation.gap_analyzer import GapAnalysis, analyze_gap
from app.db import make_session_factory
from app.providers.llm import GenerationResult, StubLLMProvider


def _make_chunk(filename: str = "doc.md", score: float = 0.15) -> RetrievedChunk:
    from uuid import uuid4
    return RetrievedChunk(
        chunk_id=str(uuid4()),
        document_id=str(uuid4()),
        filename=filename,
        chunk_index=0,
        text="Some existing content about authentication.",
        score=score,
        token_count=10,
    )


async def test_gap_analysis_returns_structured_data():
    llm = StubLLMProvider()
    payload = json.dumps({
        "missing_topic": "payment processing logic",
        "related_topics_present": ["authentication", "user accounts"],
        "suggested_document_types": ["API reference", "code module documentation"],
    })

    async def fake_generate(messages, system_prompt, **kw):
        return GenerationResult(text=payload, input_tokens=0, output_tokens=0, model="stub", stop_reason="end_turn")

    llm.generate = fake_generate
    chunks = [_make_chunk("auth.md"), _make_chunk("accounts.md")]

    result = await analyze_gap(
        user_query="How does payment work?",
        retrieved_chunks=chunks,
        session_factory=None,
        llm_provider=llm,
    )

    assert result is not None
    assert result.missing_topic == "payment processing logic"
    assert "authentication" in result.related_topics_present
    assert "API reference" in result.suggested_document_types
    assert len(result.related_document_ids) == 2


async def test_gap_analysis_llm_failure_returns_none():
    llm = StubLLMProvider()

    async def bad_generate(messages, system_prompt, **kw):
        raise RuntimeError("LLM down")

    llm.generate = bad_generate
    chunks = [_make_chunk()]

    result = await analyze_gap(
        user_query="What is X?",
        retrieved_chunks=chunks,
        session_factory=None,
        llm_provider=llm,
    )
    assert result is None


async def test_gap_analysis_malformed_json_returns_none():
    llm = StubLLMProvider()

    async def bad_json_generate(messages, system_prompt, **kw):
        return GenerationResult(text="not json at all", input_tokens=0, output_tokens=0, model="stub", stop_reason="end_turn")

    llm.generate = bad_json_generate
    result = await analyze_gap(
        user_query="What?",
        retrieved_chunks=[_make_chunk()],
        session_factory=None,
        llm_provider=llm,
    )
    assert result is None


async def test_gap_analysis_empty_chunks():
    llm = StubLLMProvider()
    payload = json.dumps({
        "missing_topic": "deployment docs",
        "related_topics_present": [],
        "suggested_document_types": ["deployment runbook"],
    })

    async def fake_generate(messages, system_prompt, **kw):
        return GenerationResult(text=payload, input_tokens=0, output_tokens=0, model="stub", stop_reason="end_turn")

    llm.generate = fake_generate
    result = await analyze_gap(
        user_query="How do we deploy?",
        retrieved_chunks=[],
        session_factory=None,
        llm_provider=llm,
    )
    assert result is not None
    assert result.related_document_ids == []
