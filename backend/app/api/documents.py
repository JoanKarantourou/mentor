from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.schemas import (
    ChunkRead,
    DocumentContentResponse,
    DocumentListItem,
    DocumentRead,
    UploadResponse,
)
from app.config import settings
from app.db import get_session
from app.models.chunk import Chunk
from app.models.document import Document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", status_code=202, response_model=UploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> UploadResponse:
    blob_store = request.app.state.blob_store
    pipeline = request.app.state.pipeline

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(data)} bytes exceeds limit of {settings.MAX_UPLOAD_SIZE_BYTES} bytes",
        )
    doc_id = uuid4()
    blob_key = f"documents/{doc_id}/{file.filename}"
    await blob_store.put(blob_key, data, file.content_type or "application/octet-stream")

    doc = Document(
        id=doc_id,
        filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        blob_path=blob_key,
        status="pending",
        file_category="document",
    )
    session.add(doc)
    await session.commit()

    background_tasks.add_task(pipeline.run, doc_id)
    return UploadResponse(document_id=doc_id, status="pending")


@router.get("", response_model=list[DocumentListItem])
async def list_documents(
    status: str | None = None,
    file_category: str | None = None,
    scope: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[DocumentListItem]:
    limit = min(limit, 500)
    stmt = select(Document).where(Document.deleted_at == None)  # noqa: E711
    if status:
        stmt = stmt.where(Document.status == status)
    if file_category:
        stmt = stmt.where(Document.file_category == file_category)
    if scope:
        stmt = stmt.where(Document.scope == scope)
    stmt = stmt.offset(offset).limit(limit)
    results = await session.exec(stmt)
    return [DocumentListItem.model_validate(d) for d in results.all()]


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> DocumentRead:
    doc = await session.get(Document, document_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentRead.model_validate(doc)


@router.get("/{document_id}/content", response_model=DocumentContentResponse)
async def get_document_content(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> DocumentContentResponse:
    doc = await session.get(Document, document_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status not in ("ready", "chunking", "embedding", "indexed"):
        raise HTTPException(
            status_code=409,
            detail=f"Document not ready (status: {doc.status})",
        )
    return DocumentContentResponse(
        document_id=document_id,
        content=doc.normalized_content or "",
        detected_language=doc.detected_language,
    )


@router.get("/{document_id}/chunks", response_model=list[ChunkRead])
async def get_document_chunks(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[ChunkRead]:
    doc = await session.get(Document, document_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "indexed":
        raise HTTPException(
            status_code=409,
            detail=f"Document not indexed (status: {doc.status})",
        )
    stmt = (
        select(Chunk)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index)
    )
    results = await session.exec(stmt)
    return [ChunkRead.model_validate(c) for c in results.all()]


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    doc = await session.get(Document, document_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.deleted_at = datetime.now(UTC)
    await session.commit()
