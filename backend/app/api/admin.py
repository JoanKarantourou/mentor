from fastapi import APIRouter, Depends, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.ingestion.embedding import embed_chunks
from app.models.document import Document

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reindex", status_code=202)
async def reindex(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    embedding_provider = request.app.state.embedding_provider
    session_factory = request.app.state.session_factory

    stmt = select(Document).where(
        Document.deleted_at == None,  # noqa: E711
        Document.status == "indexed",
    )
    results = await session.exec(stmt)
    docs = results.all()

    for doc in docs:
        await embed_chunks(doc.id, session_factory, embedding_provider)

    return {"reindexed": len(docs)}
