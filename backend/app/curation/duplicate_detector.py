"""Near-duplicate detection for uploaded documents."""
from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.ingestion.chunking import get_chunker
from app.providers.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)

_MAX_CHUNKS_TO_CHECK = 60  # cap to avoid O(n) DB round-trips on huge docs


@dataclass
class DuplicateMatch:
    existing_document_id: UUID
    existing_filename: str
    similarity: float
    match_type: Literal["exact", "near_duplicate"]
    matching_chunks: int


async def find_duplicates(
    new_content: str,
    new_document_user_id: str,
    file_category: str,
    filename: str,
    session_factory: Callable[[], AsyncSession],
    embedding_provider: EmbeddingProvider,
    threshold_near: float = 0.92,
    threshold_exact: float = 0.99,
    match_ratio: float = 0.5,
) -> list[DuplicateMatch]:
    """Return existing documents that are near-duplicates of the new content."""
    content_hash = hashlib.sha256(new_content.encode()).hexdigest()

    # Exact match via content hash
    async with session_factory() as session:
        exact = await session.execute(
            text("""
                SELECT d.id, d.filename
                FROM documents d
                WHERE d.deleted_at IS NULL
                  AND d.normalized_content IS NOT NULL
                  AND md5(d.normalized_content) = md5(:content)
                  AND length(d.normalized_content) = :content_len
            """),
            {"content": new_content, "content_len": len(new_content)},
        )
        exact_rows = exact.all()

    if exact_rows:
        return [
            DuplicateMatch(
                existing_document_id=UUID(str(r.id)),
                existing_filename=r.filename,
                similarity=1.0,
                match_type="exact",
                matching_chunks=0,
            )
            for r in exact_rows
        ]

    # Near-duplicate: chunk the new content, embed, search
    chunker = get_chunker(file_category, filename)
    text_chunks = chunker.chunk(new_content)
    if not text_chunks:
        return []

    # Sample chunks to keep DB round-trips bounded
    if len(text_chunks) > _MAX_CHUNKS_TO_CHECK:
        step = len(text_chunks) // _MAX_CHUNKS_TO_CHECK
        text_chunks = text_chunks[::step][:_MAX_CHUNKS_TO_CHECK]

    try:
        vectors = await embedding_provider.embed([c.text for c in text_chunks])
    except Exception as exc:
        logger.warning("duplicate detection embedding failed: %s", exc)
        return []

    # For each new chunk, find the best matching existing chunk and its document
    doc_match_counts: dict[str, int] = {}
    doc_best_sim: dict[str, float] = {}
    doc_filename: dict[str, str] = {}

    async with session_factory() as session:
        for vec in vectors:
            vec_str = "[" + ",".join(str(v) for v in vec) + "]"
            result = await session.execute(
                text("""
                    SELECT c.document_id, d.filename,
                           1 - (c.embedding <=> CAST(:vec AS vector)) AS score
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    WHERE c.embedding IS NOT NULL AND d.deleted_at IS NULL
                    ORDER BY c.embedding <=> CAST(:vec AS vector)
                    LIMIT 1
                """),
                {"vec": vec_str},
            )
            row = result.first()
            if row and float(row.score) >= threshold_near:
                doc_id = str(row.document_id)
                doc_match_counts[doc_id] = doc_match_counts.get(doc_id, 0) + 1
                doc_best_sim[doc_id] = max(doc_best_sim.get(doc_id, 0.0), float(row.score))
                doc_filename[doc_id] = row.filename

    matches: list[DuplicateMatch] = []
    total_chunks = len(vectors)
    for doc_id, match_count in doc_match_counts.items():
        if match_count / total_chunks >= match_ratio:
            matches.append(
                DuplicateMatch(
                    existing_document_id=UUID(doc_id),
                    existing_filename=doc_filename[doc_id],
                    similarity=doc_best_sim[doc_id],
                    match_type="near_duplicate",
                    matching_chunks=match_count,
                )
            )

    matches.sort(key=lambda m: m.similarity, reverse=True)
    return matches
