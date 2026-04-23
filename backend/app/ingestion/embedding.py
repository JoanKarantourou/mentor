import asyncio
import logging
import time
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import delete
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.ingestion.chunking import get_chunker
from app.ingestion.chunking.base import TextChunk
from app.models.chunk import Chunk
from app.models.document import Document
from app.providers.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)

_INTER_BATCH_PAUSE_THRESHOLD = 10  # pause between batches when a document yields > this many
_INTER_BATCH_PAUSE_SECONDS = 0.2


async def embed_chunks(
    document_id: UUID,
    session_factory: Callable[[], AsyncSession],
    embedding_provider: EmbeddingProvider,
) -> None:
    async with session_factory() as session:
        doc = await session.get(Document, document_id)
        if doc is None or not doc.normalized_content:
            return
        text = doc.normalized_content
        file_category = doc.file_category
        filename = doc.filename

    chunker = get_chunker(file_category, filename)
    text_chunks: list[TextChunk] = chunker.chunk(text)

    async with session_factory() as session:
        await session.exec(delete(Chunk).where(Chunk.document_id == document_id))  # type: ignore[arg-type]
        await session.commit()

    batch_size = settings.EMBEDDING_BATCH_SIZE
    total_batches = max(1, (len(text_chunks) + batch_size - 1) // batch_size)
    chunk_index = 0

    for batch_num, i in enumerate(range(0, len(text_chunks), batch_size)):
        batch = text_chunks[i : i + batch_size]
        texts = [c.text for c in batch]
        tokens_in_batch = sum(c.token_count for c in batch)

        start = time.monotonic()
        try:
            vectors = await embedding_provider.embed(texts)
        except Exception as exc:
            logger.error(
                "embed_batch FAILED document_id=%s batch=%d/%d: %s",
                document_id,
                batch_num + 1,
                total_batches,
                exc,
            )
            async with session_factory() as session:
                doc = await session.get(Document, document_id)
                if doc is not None:
                    doc.status = "failed"
                    doc.error_message = f"Embedding failed after retries: {exc}"[:2000]
                    session.add(doc)
                    await session.commit()
            return

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "embed_batch document_id=%s batch=%d/%d chunks=%d tokens=%d "
            "duration_ms=%.0f provider=%s",
            document_id,
            batch_num + 1,
            total_batches,
            len(batch),
            tokens_in_batch,
            duration_ms,
            embedding_provider.identifier,
        )

        chunks = [
            Chunk(
                document_id=document_id,
                chunk_index=chunk_index + j,
                text=tc.text,
                token_count=tc.token_count,
                embedding=vec,
                embedding_model=embedding_provider.identifier,
                meta=tc.meta,
            )
            for j, (tc, vec) in enumerate(zip(batch, vectors))
        ]
        chunk_index += len(batch)

        async with session_factory() as session:
            for chunk in chunks:
                session.add(chunk)
            await session.commit()

        if total_batches > _INTER_BATCH_PAUSE_THRESHOLD and batch_num < total_batches - 1:
            await asyncio.sleep(_INTER_BATCH_PAUSE_SECONDS)
