"""Curation API: memory extraction, duplicate resolution."""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.ingestion.language import detect_language
from app.models.conversation import Conversation
from app.models.document import Document

router = APIRouter(tags=["curation"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ExtractMemoryRequest(BaseModel):
    approve: bool = False
    title_override: str | None = None
    content_override: str | None = None


class ExtractMemoryResponse(BaseModel):
    title: str
    content: str
    fact_count: int
    source_message_count: int


class SavedMemoryResponse(BaseModel):
    document_id: UUID


class MemoryStatusResponse(BaseModel):
    should_suggest: bool
    trigger_reason: str | None
    messages_since_last_extract: int


class DuplicateMatchResponse(BaseModel):
    existing_document_id: UUID
    existing_filename: str
    similarity: float
    match_type: str
    matching_chunks: int


class ResolveDuplicateRequest(BaseModel):
    action: str  # "replace" | "keep_both" | "skip"
    replace_target_id: UUID | None = None


# ---------------------------------------------------------------------------
# POST /conversations/{id}/extract-memory
# ---------------------------------------------------------------------------


@router.post("/conversations/{conversation_id}/extract-memory")
async def extract_memory_endpoint(
    conversation_id: UUID,
    body: ExtractMemoryRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    conv = await session.get(Conversation, conversation_id)
    if conv is None or conv.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    llm_provider = request.app.state.llm_provider
    session_factory = request.app.state.session_factory

    try:
        from app.curation.memory_extractor import extract_memory
        memory = await extract_memory(conversation_id, session_factory, llm_provider)
    except Exception as exc:
        logger.error("memory extraction failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}")

    # Apply overrides if provided
    title = body.title_override or memory.title
    content = body.content_override or memory.content

    if not body.approve:
        return ExtractMemoryResponse(
            title=title,
            content=content,
            fact_count=memory.fact_count,
            source_message_count=len(memory.source_message_ids),
        )

    # Save as Document
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "-").lower()[:50]
    filename = f"chat-extract-{safe_title}-{date_str}.md"

    blob_store = request.app.state.blob_store
    pipeline = request.app.state.pipeline

    doc_id = uuid4()
    blob_key = f"documents/{doc_id}/{filename}"
    await blob_store.put(blob_key, content.encode(), "text/markdown")

    detected_lang = detect_language(content)

    doc = Document(
        id=doc_id,
        filename=filename,
        content_type="text/markdown",
        size_bytes=len(content.encode()),
        blob_path=blob_key,
        normalized_content=content,
        detected_language=detected_lang,
        file_category="document",
        status="ready",
        uploaded_by=conv.user_id,
        scope="private",
        source_type="chat_extract",
        source_conversation_id=conversation_id,
    )
    session.add(doc)
    await session.commit()

    # Kick off embedding in the background
    background_tasks.add_task(pipeline.resume_ingestion, doc_id)

    return SavedMemoryResponse(document_id=doc_id)


# ---------------------------------------------------------------------------
# GET /conversations/{id}/memory-status
# ---------------------------------------------------------------------------


@router.get("/conversations/{conversation_id}/memory-status")
async def memory_status(
    conversation_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> MemoryStatusResponse:
    conv = await session.get(Conversation, conversation_id)
    if conv is None or conv.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    from sqlalchemy import text as sql_text

    session_factory = request.app.state.session_factory
    embedding_provider = request.app.state.embedding_provider
    cfg = request.app.state.chat_config

    async with session_factory() as sf_session:
        result = await sf_session.execute(
            sql_text("SELECT COUNT(*) FROM messages WHERE conversation_id = :cid"),
            {"cid": str(conversation_id)},
        )
        total_msgs = result.scalar() or 0

    if total_msgs < cfg.get("memory_extraction_min_messages", 12):
        return MemoryStatusResponse(
            should_suggest=False,
            trigger_reason=None,
            messages_since_last_extract=int(total_msgs),
        )

    # Count extracts already saved for this conversation
    existing = (
        await session.exec(
            select(Document).where(
                Document.source_conversation_id == conversation_id,
                Document.source_type == "chat_extract",
                Document.deleted_at.is_(None),
            )
        )
    ).all()
    last_extract_msg_count = len(existing) * cfg.get("memory_extraction_min_messages", 12)
    msgs_since = int(total_msgs) - last_extract_msg_count

    try:
        from app.curation.triggers import check_memory_trigger
        trigger = await check_memory_trigger(
            conversation_id=conversation_id,
            current_user_message="",
            session_factory=session_factory,
            embedding_provider=embedding_provider,
            min_messages=cfg.get("memory_extraction_min_messages", 12),
            topic_shift_threshold=cfg.get("memory_extraction_topic_shift_threshold", 0.5),
            session_break_minutes=cfg.get("memory_extraction_session_break_minutes", 30),
        )
        return MemoryStatusResponse(
            should_suggest=trigger.should_suggest,
            trigger_reason=trigger.reason,
            messages_since_last_extract=msgs_since,
        )
    except Exception as exc:
        logger.warning("memory status check failed: %s", exc)
        return MemoryStatusResponse(
            should_suggest=False,
            trigger_reason=None,
            messages_since_last_extract=msgs_since,
        )


# ---------------------------------------------------------------------------
# GET /documents/{id}/duplicates
# ---------------------------------------------------------------------------


@router.get("/documents/{document_id}/duplicates")
async def get_duplicates(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[DuplicateMatchResponse]:
    doc = await session.get(Document, document_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "awaiting_user_decision":
        raise HTTPException(
            status_code=409,
            detail=f"Document is not awaiting duplicate resolution (status: {doc.status})",
        )
    if not doc.duplicate_check:
        return []
    return [
        DuplicateMatchResponse(
            existing_document_id=UUID(m["existing_document_id"]),
            existing_filename=m["existing_filename"],
            similarity=m["similarity"],
            match_type=m["match_type"],
            matching_chunks=m["matching_chunks"],
        )
        for m in doc.duplicate_check
    ]


# ---------------------------------------------------------------------------
# POST /documents/{id}/resolve-duplicate
# ---------------------------------------------------------------------------


@router.post("/documents/{document_id}/resolve-duplicate", status_code=204)
async def resolve_duplicate(
    document_id: UUID,
    body: ResolveDuplicateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> None:
    doc = await session.get(Document, document_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "awaiting_user_decision":
        raise HTTPException(
            status_code=409,
            detail=f"Document is not awaiting duplicate resolution (status: {doc.status})",
        )

    if body.action not in ("replace", "keep_both", "skip"):
        raise HTTPException(status_code=400, detail="action must be replace, keep_both, or skip")

    pipeline = request.app.state.pipeline
    blob_store = request.app.state.blob_store

    if body.action == "skip":
        blob_path = doc.blob_path
        doc.status = "skipped_duplicate"
        await session.commit()
        try:
            await blob_store.delete(blob_path)
        except Exception as exc:
            logger.warning("blob delete failed for skipped doc %s: %s", document_id, exc)
        return

    if body.action == "replace" and body.replace_target_id is not None:
        target = await session.get(Document, body.replace_target_id)
        if target is not None and target.deleted_at is None:
            target.deleted_at = datetime.now(UTC)
            session.add(target)

    # Clear duplicate_check and continue ingestion
    doc.duplicate_check = None
    await session.commit()

    background_tasks.add_task(pipeline.resume_ingestion, document_id)
