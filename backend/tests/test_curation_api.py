"""Tests for curation API endpoints."""
from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.conversation import Conversation
from app.models.document import Document
from app.models.message import Message
from app.providers.llm import GenerationResult


async def _seed_conversation(session: AsyncSession, msg_count: int = 14) -> UUID:
    conv = Conversation(user_id="dev")
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    conv_id = conv.id  # capture before second commit
    for i in range(msg_count):
        role = "user" if i % 2 == 0 else "assistant"
        session.add(Message(
            conversation_id=conv_id,
            role=role,
            content=f"message {i}",
            message_index=i,
        ))
    await session.commit()
    return conv_id


async def _seed_duplicate_doc(session: AsyncSession, content: str = "dup content") -> UUID:
    doc = Document(
        filename="existing.md",
        content_type="text/markdown",
        size_bytes=len(content.encode()),
        blob_path=f"documents/{uuid4()}/existing.md",
        normalized_content=content,
        file_category="document",
        status="awaiting_user_decision",
        uploaded_by="dev",
        duplicate_check=[
            {
                "existing_document_id": str(uuid4()),
                "existing_filename": "original.md",
                "similarity": 0.95,
                "match_type": "near_duplicate",
                "matching_chunks": 3,
            }
        ],
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc.id  # return UUID, not the object


# ---------------------------------------------------------------------------
# Memory extraction — preview
# ---------------------------------------------------------------------------


async def test_extract_memory_preview(async_client: AsyncClient, test_engine: AsyncEngine):
    async with AsyncSession(test_engine) as session:
        conv_id = await _seed_conversation(session)

    payload = json.dumps({
        "title": "Test decisions",
        "facts": [{"content": "We chose Redis.", "source_message_indices": [1]}],
    })

    from app.main import app
    llm = app.state.llm_provider

    async def fake_generate(messages, system_prompt, **kw):
        return GenerationResult(text=payload, input_tokens=0, output_tokens=0, model="stub", stop_reason="end_turn")

    original = llm.generate
    llm.generate = fake_generate
    try:
        resp = await async_client.post(
            f"/conversations/{conv_id}/extract-memory",
            json={"approve": False},
        )
    finally:
        llm.generate = original

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Test decisions"
    assert "Redis" in data["content"]
    assert data["fact_count"] == 1


async def test_extract_memory_approve_creates_document(async_client: AsyncClient, test_engine: AsyncEngine):
    async with AsyncSession(test_engine) as session:
        conv_id = await _seed_conversation(session)

    payload = json.dumps({
        "title": "Redis caching decision",
        "facts": [{"content": "We chose Redis.", "source_message_indices": [1]}],
    })

    from app.main import app
    llm = app.state.llm_provider

    async def fake_generate(messages, system_prompt, **kw):
        return GenerationResult(text=payload, input_tokens=0, output_tokens=0, model="stub", stop_reason="end_turn")

    llm.generate = fake_generate
    try:
        resp = await async_client.post(
            f"/conversations/{conv_id}/extract-memory",
            json={"approve": True},
        )
    finally:
        llm.generate = fake_generate  # keep for bg task

    assert resp.status_code == 200
    data = resp.json()
    assert "document_id" in data

    async with AsyncSession(test_engine) as session:
        doc = await session.get(Document, data["document_id"])
    assert doc is not None
    assert doc.source_type == "chat_extract"
    assert doc.source_conversation_id == conv_id
    assert "Redis" in (doc.normalized_content or "")


async def test_extract_memory_with_overrides(async_client: AsyncClient, test_engine: AsyncEngine):
    async with AsyncSession(test_engine) as session:
        conv_id = await _seed_conversation(session)

    from app.main import app
    llm = app.state.llm_provider

    async def fake_generate(messages, system_prompt, **kw):
        return GenerationResult(
            text=json.dumps({"title": "original title", "facts": []}),
            input_tokens=0, output_tokens=0, model="stub", stop_reason="end_turn",
        )

    llm.generate = fake_generate
    resp = await async_client.post(
        f"/conversations/{conv_id}/extract-memory",
        json={"approve": True, "title_override": "My custom title", "content_override": "Custom content."},
    )
    assert resp.status_code == 200
    data = resp.json()
    async with AsyncSession(test_engine) as session:
        doc = await session.get(Document, data["document_id"])
    assert "my-custom-title" in doc.filename
    assert doc.normalized_content == "Custom content."


async def test_extract_memory_not_found(async_client: AsyncClient):
    resp = await async_client.post(
        f"/conversations/{uuid4()}/extract-memory",
        json={"approve": False},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Duplicate endpoints
# ---------------------------------------------------------------------------


async def test_get_duplicates(async_client: AsyncClient, test_engine: AsyncEngine):
    async with AsyncSession(test_engine) as session:
        doc_id = await _seed_duplicate_doc(session)

    resp = await async_client.get(f"/documents/{doc_id}/duplicates")
    assert resp.status_code == 200
    matches = resp.json()
    assert len(matches) == 1
    assert matches[0]["match_type"] == "near_duplicate"
    assert matches[0]["similarity"] == 0.95


async def test_get_duplicates_not_awaiting_decision(async_client: AsyncClient, test_engine: AsyncEngine):
    async with AsyncSession(test_engine) as session:
        doc = Document(
            filename="ready.md",
            content_type="text/markdown",
            size_bytes=10,
            blob_path=f"documents/{uuid4()}/ready.md",
            file_category="document",
            status="indexed",
            uploaded_by="dev",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

    resp = await async_client.get(f"/documents/{doc_id}/duplicates")
    assert resp.status_code == 409


async def test_resolve_duplicate_keep_both(async_client: AsyncClient, test_engine: AsyncEngine):
    async with AsyncSession(test_engine) as session:
        doc_id = await _seed_duplicate_doc(session)

    resp = await async_client.post(
        f"/documents/{doc_id}/resolve-duplicate",
        json={"action": "keep_both"},
    )
    assert resp.status_code == 204

    async with AsyncSession(test_engine) as session:
        updated = await session.get(Document, doc_id)
    assert updated.duplicate_check is None


async def test_resolve_duplicate_skip(async_client: AsyncClient, test_engine: AsyncEngine):
    async with AsyncSession(test_engine) as session:
        doc_id = await _seed_duplicate_doc(session)

    resp = await async_client.post(
        f"/documents/{doc_id}/resolve-duplicate",
        json={"action": "skip"},
    )
    assert resp.status_code == 204

    async with AsyncSession(test_engine) as session:
        updated = await session.get(Document, doc_id)
    assert updated.status == "skipped_duplicate"


async def test_resolve_duplicate_replace(async_client: AsyncClient, test_engine: AsyncEngine):
    async with AsyncSession(test_engine) as session:
        target = Document(
            filename="old.md",
            content_type="text/markdown",
            size_bytes=5,
            blob_path=f"documents/{uuid4()}/old.md",
            file_category="document",
            status="indexed",
            uploaded_by="dev",
        )
        session.add(target)
        await session.commit()
        await session.refresh(target)
        target_id = target.id
        doc_id = await _seed_duplicate_doc(session)

    resp = await async_client.post(
        f"/documents/{doc_id}/resolve-duplicate",
        json={"action": "replace", "replace_target_id": str(target_id)},
    )
    assert resp.status_code == 204

    async with AsyncSession(test_engine) as session:
        old = await session.get(Document, target_id)
    assert old.deleted_at is not None


async def test_resolve_duplicate_invalid_action(async_client: AsyncClient, test_engine: AsyncEngine):
    async with AsyncSession(test_engine) as session:
        doc_id = await _seed_duplicate_doc(session)

    resp = await async_client.post(
        f"/documents/{doc_id}/resolve-duplicate",
        json={"action": "explode"},
    )
    assert resp.status_code == 400
