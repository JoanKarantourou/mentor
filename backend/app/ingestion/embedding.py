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
    all_chunks: list[Chunk] = []
    for i in range(0, len(text_chunks), batch_size):
        batch = text_chunks[i : i + batch_size]
        texts = [c.text for c in batch]
        vectors = await embedding_provider.embed(texts)
        for j, (tc, vec) in enumerate(zip(batch, vectors)):
            all_chunks.append(
                Chunk(
                    document_id=document_id,
                    chunk_index=i + j,
                    text=tc.text,
                    token_count=tc.token_count,
                    embedding=vec,
                    embedding_model=embedding_provider.identifier,
                    meta=tc.meta,
                )
            )

    async with session_factory() as session:
        for chunk in all_chunks:
            session.add(chunk)
        await session.commit()
