"""Search edge cases: empty corpus, deleted documents, zero matches, self-consistency."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.document import Document


# ---------------------------------------------------------------------------
# Empty corpus
# ---------------------------------------------------------------------------


async def test_search_empty_corpus(async_client: AsyncClient) -> None:
    resp = await async_client.post("/search", json={"query": "anything"})
    assert resp.status_code == 200
    assert resp.json()["hits"] == []


# ---------------------------------------------------------------------------
# All documents soft-deleted
# ---------------------------------------------------------------------------


async def test_search_all_documents_deleted(
    async_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    from datetime import UTC, datetime

    # Create a document and mark it deleted
    async with AsyncSession(test_engine) as session:
        doc = Document(
            filename="deleted.md",
            content_type="text/markdown",
            size_bytes=10,
            blob_path="test/deleted.md",
            status="indexed",
        )
        session.add(doc)
        await session.flush()
        doc.deleted_at = datetime.now(UTC)
        session.add(doc)
        await session.commit()

    resp = await async_client.post("/search", json={"query": "deleted content"})
    assert resp.status_code == 200
    assert resp.json()["hits"] == []


# ---------------------------------------------------------------------------
# Query exactly matches chunk content — should rank first with high score
# ---------------------------------------------------------------------------


async def test_search_exact_match_ranks_first(
    async_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    from app.providers.embeddings import StubEmbeddingProvider
    from sqlalchemy import text

    provider = StubEmbeddingProvider()
    unique_text = "unique_sentinel_phrase_xq7z"

    vec = (await provider.embed([unique_text]))[0]
    vec_str = "[" + ",".join(str(v) for v in vec) + "]"

    async with AsyncSession(test_engine) as session:
        doc = Document(
            filename="sentinel.md",
            content_type="text/markdown",
            size_bytes=len(unique_text),
            blob_path="test/sentinel.md",
            status="indexed",
        )
        session.add(doc)
        await session.flush()

        await session.execute(
            text("""
                INSERT INTO chunks (id, document_id, chunk_index, text, token_count, embedding, embedding_model, created_at)
                VALUES (
                    :cid, :did, 0, :txt, 10,
                    CAST(:vec AS vector),
                    'stub-v1',
                    NOW()
                )
            """),
            {
                "cid": str(uuid4()),
                "did": str(doc.id),
                "txt": unique_text,
                "vec": vec_str,
            },
        )
        await session.commit()

    resp = await async_client.post("/search", json={"query": unique_text, "limit": 1})
    assert resp.status_code == 200
    results = resp.json()["hits"]
    assert len(results) >= 1
    # Self-similarity: same embedding → score close to 1.0
    assert results[0]["score"] > 0.95


# ---------------------------------------------------------------------------
# Filter combination produces zero matches
# ---------------------------------------------------------------------------


async def test_search_filter_zero_matches(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/search",
        json={"query": "anything", "file_category": "code"},
    )
    assert resp.status_code == 200
    # Empty corpus → empty result, not error
    assert resp.json()["hits"] == []
