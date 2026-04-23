from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import distinct, func, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.ingestion.embedding import embed_chunks
from app.models.chunk import Chunk
from app.models.document import Document

router = APIRouter(prefix="/admin", tags=["admin"])


class ReindexRequest(BaseModel):
    only_stale: bool = False


@router.post("/reindex", status_code=202)
async def reindex(
    request: Request,
    body: ReindexRequest = ReindexRequest(),
    session: AsyncSession = Depends(get_session),
) -> dict:
    embedding_provider = request.app.state.embedding_provider
    session_factory = request.app.state.session_factory
    current_id = embedding_provider.identifier

    if body.only_stale:
        # Documents that have at least one chunk with a different embedding_model.
        stale_doc_ids_stmt = (
            select(distinct(Chunk.document_id))
            .where(
                or_(Chunk.embedding_model.is_(None), Chunk.embedding_model != current_id)
            )
        )
        stale_ids_result = await session.exec(stale_doc_ids_stmt)
        stale_ids: set[UUID] = set(stale_ids_result.all())

        if not stale_ids:
            return {"reindexed": 0}

        stmt = select(Document).where(
            Document.deleted_at == None,  # noqa: E711
            Document.status == "indexed",
            Document.id.in_(stale_ids),  # type: ignore[attr-defined]
        )
    else:
        stmt = select(Document).where(
            Document.deleted_at == None,  # noqa: E711
            Document.status == "indexed",
        )

    results = await session.exec(stmt)
    docs = results.all()

    succeeded = 0
    for doc in docs:
        await embed_chunks(doc.id, session_factory, embedding_provider)
        succeeded += 1

    return {"reindexed": succeeded}


@router.get("/embeddings/status")
async def embeddings_status(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    embedding_provider = request.app.state.embedding_provider
    current_id = embedding_provider.identifier

    # Chunk counts grouped by embedding model.
    counts_stmt = select(Chunk.embedding_model, func.count(Chunk.id)).group_by(
        Chunk.embedding_model
    )
    counts_result = await session.exec(counts_stmt)
    chunks_by_model: dict[str, int] = {
        (model if model is not None else "unknown"): count
        for model, count in counts_result.all()
    }

    # Stale = embedding_model is NULL or differs from current provider.
    stale_filter = or_(Chunk.embedding_model.is_(None), Chunk.embedding_model != current_id)

    stale_chunks_stmt = select(func.count(Chunk.id)).where(stale_filter)
    stale_chunks: int = (await session.exec(stale_chunks_stmt)).one()

    stale_docs_stmt = select(func.count(distinct(Chunk.document_id))).where(stale_filter)
    stale_documents: int = (await session.exec(stale_docs_stmt)).one()

    return {
        "current_provider_identifier": current_id,
        "chunks_by_model": chunks_by_model,
        "stale_chunks": stale_chunks,
        "stale_documents": stale_documents,
    }
