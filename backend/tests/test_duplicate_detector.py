"""Tests for duplicate detection."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.curation.duplicate_detector import DuplicateMatch, find_duplicates
from app.db import make_session_factory
from app.models.chunk import Chunk
from app.models.document import Document
from app.providers.embeddings import StubEmbeddingProvider


# ---------------------------------------------------------------------------
# Embedder that returns the same unit vector for every text.
# This guarantees cosine similarity = 1.0 between any two texts so that
# near-duplicate detection works predictably in tests.
# ---------------------------------------------------------------------------

import math


class _ConstantEmbedder(StubEmbeddingProvider):
    def __init__(self, value: float = 1.0):
        self._value = value

    async def embed(self, texts: list[str]) -> list[list[float]]:
        dim = 1536
        v = [self._value / math.sqrt(dim)] * dim
        return [v for _ in texts]


async def _make_indexed_doc(
    session: AsyncSession,
    content: str,
    filename: str = "doc.md",
    embedder: StubEmbeddingProvider | None = None,
) -> UUID:
    from app.ingestion.chunking import get_chunker

    if embedder is None:
        embedder = _ConstantEmbedder()

    doc = Document(
        filename=filename,
        content_type="text/markdown",
        size_bytes=len(content.encode()),
        blob_path=f"documents/{uuid4()}/{filename}",
        normalized_content=content,
        file_category="document",
        status="indexed",
        uploaded_by="dev",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    doc_id = doc.id  # capture before adding chunks (second commit)

    chunker = get_chunker("document", filename)
    text_chunks = chunker.chunk(content)
    for i, tc in enumerate(text_chunks[:5]):
        vecs = await embedder.embed([tc.text])
        session.add(Chunk(
            document_id=doc_id,
            chunk_index=i,
            text=tc.text,
            token_count=tc.token_count,
            embedding=vecs[0],
            embedding_model="stub",
            meta={},
        ))
    await session.commit()
    return doc_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_exact_duplicate_detected(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    content = "This is some important documentation about the authentication service."
    async with AsyncSession(test_engine) as session:
        existing_id = await _make_indexed_doc(session, content)

    matches = await find_duplicates(
        new_content=content,
        new_document_user_id="dev",
        file_category="document",
        filename="auth-docs.md",
        session_factory=sf,
        embedding_provider=_ConstantEmbedder(),
    )
    assert len(matches) >= 1
    assert matches[0].match_type == "exact"
    assert matches[0].similarity == 1.0
    assert matches[0].existing_document_id == existing_id


async def test_different_content_no_exact_match(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    async with AsyncSession(test_engine) as session:
        await _make_indexed_doc(session, "Authentication service documentation here.")

    matches = await find_duplicates(
        new_content="Payment processing and billing service overview.",
        new_document_user_id="dev",
        file_category="document",
        filename="billing.md",
        session_factory=sf,
        embedding_provider=_ConstantEmbedder(),
    )
    # Exact duplicate should not match (different content hash)
    exact_matches = [m for m in matches if m.match_type == "exact"]
    assert len(exact_matches) == 0


async def test_near_duplicate_detected(test_engine: AsyncEngine):
    """Constant embedder → similarity 1.0 for any pair → guaranteed near-duplicate."""
    sf = make_session_factory(test_engine)
    base_content = "The ingestion pipeline processes documents through five stages."
    async with AsyncSession(test_engine) as session:
        existing_id = await _make_indexed_doc(session, base_content, embedder=_ConstantEmbedder())

    slightly_different = base_content + "\n\nAn additional paragraph with new information."

    matches = await find_duplicates(
        new_content=slightly_different,
        new_document_user_id="dev",
        file_category="document",
        filename="ingestion-v2.md",
        session_factory=sf,
        embedding_provider=_ConstantEmbedder(),
        threshold_near=0.9,
        match_ratio=0.5,
    )
    near = [m for m in matches if m.match_type == "near_duplicate"]
    assert len(near) >= 1
    assert near[0].existing_document_id == existing_id


async def test_no_match_empty_corpus(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    matches = await find_duplicates(
        new_content="Some new content.",
        new_document_user_id="dev",
        file_category="document",
        filename="new.md",
        session_factory=sf,
        embedding_provider=_ConstantEmbedder(),
    )
    assert matches == []


async def test_embedding_failure_returns_empty(test_engine: AsyncEngine):
    sf = make_session_factory(test_engine)
    async with AsyncSession(test_engine) as session:
        await _make_indexed_doc(session, "Some existing content.")

    async def bad_embed(texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embed down")

    embedder = _ConstantEmbedder()
    embedder.embed = bad_embed  # type: ignore[method-assign]

    matches = await find_duplicates(
        new_content="Different content entirely, no hash match.",
        new_document_user_id="dev",
        file_category="document",
        filename="other.md",
        session_factory=sf,
        embedding_provider=embedder,
    )
    assert matches == []
