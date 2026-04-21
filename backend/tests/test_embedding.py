"""Tests for embedding provider and embed_chunks orchestration."""

import math
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import make_session_factory
from app.ingestion.embedding import embed_chunks
from app.models.chunk import Chunk
from app.models.document import Document
from app.providers.embeddings import StubEmbeddingProvider
from app.storage.local import LocalBlobStore

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# StubEmbeddingProvider
# ---------------------------------------------------------------------------


async def test_stub_embed_returns_normalized_vectors() -> None:
    provider = StubEmbeddingProvider()
    vecs = await provider.embed(["hello world", "foo bar"])
    assert len(vecs) == 2
    for vec in vecs:
        assert len(vec) == 1536
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-5


async def test_stub_embed_is_deterministic() -> None:
    provider = StubEmbeddingProvider()
    vecs1 = await provider.embed(["test text"])
    vecs2 = await provider.embed(["test text"])
    assert vecs1 == vecs2


async def test_stub_different_texts_give_different_vectors() -> None:
    provider = StubEmbeddingProvider()
    vecs = await provider.embed(["hello", "world"])
    assert vecs[0] != vecs[1]


def test_stub_identifier() -> None:
    assert StubEmbeddingProvider().identifier == "stub-v1"


# ---------------------------------------------------------------------------
# embed_chunks integration
# ---------------------------------------------------------------------------


async def _insert_ready_doc(
    sf,
    blob_store: LocalBlobStore,
    filename: str,
    content_type: str,
    normalized_content: str,
    file_category: str = "document",
) -> Document:
    doc_id = uuid.uuid4()
    blob_key = f"documents/{doc_id}/{filename}"
    await blob_store.put(blob_key, b"placeholder", content_type)
    doc = Document(
        id=doc_id,
        filename=filename,
        content_type=content_type,
        size_bytes=0,
        blob_path=blob_key,
        status="ready",
        file_category=file_category,
        normalized_content=normalized_content,
    )
    async with sf() as session:
        session.add(doc)
        await session.commit()
    return doc


async def test_embed_chunks_creates_chunks(
    test_engine: AsyncEngine,
    tmp_blob_store: LocalBlobStore,
) -> None:
    sf = make_session_factory(test_engine)
    text = (FIXTURES / "sample.md").read_text(encoding="utf-8")
    doc = await _insert_ready_doc(sf, tmp_blob_store, "sample.md", "text/markdown", text)

    await embed_chunks(doc.id, sf, StubEmbeddingProvider())

    async with AsyncSession(test_engine) as session:
        stmt = select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.chunk_index)
        results = await session.exec(stmt)
        chunks = results.all()

    assert len(chunks) >= 1
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i
        assert chunk.text.strip()
        assert chunk.token_count > 0
        assert chunk.embedding is not None
        assert len(chunk.embedding) == 1536
        assert chunk.embedding_model == "stub-v1"


async def test_embed_chunks_replaces_existing(
    test_engine: AsyncEngine,
    tmp_blob_store: LocalBlobStore,
) -> None:
    sf = make_session_factory(test_engine)
    text = "Short text for testing re-indexing."
    doc = await _insert_ready_doc(sf, tmp_blob_store, "test.md", "text/markdown", text)

    provider = StubEmbeddingProvider()
    await embed_chunks(doc.id, sf, provider)
    await embed_chunks(doc.id, sf, provider)

    async with AsyncSession(test_engine) as session:
        stmt = select(Chunk).where(Chunk.document_id == doc.id)
        results = await session.exec(stmt)
        chunks = results.all()

    assert len(chunks) >= 1
    indices = [c.chunk_index for c in chunks]
    assert indices == sorted(indices)
    assert len(set(indices)) == len(indices)
