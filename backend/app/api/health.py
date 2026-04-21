from fastapi import APIRouter, Request
from sqlalchemy import text

from app.config import settings
from app.db import engine

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    db_status = await _check_db()
    blob_status = await _check_blob_store(request)
    return {
        "status": "ok",
        "database": db_status,
        "blob_store": blob_status,
        "llm_provider": settings.LLM_PROVIDER,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
    }


async def _check_db() -> str:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


async def _check_blob_store(request: Request) -> str:
    try:
        blob_store = getattr(request.app.state, "blob_store", None)
        if blob_store is None:
            return "not configured"
        await blob_store.put("_health/ping", b"ok", "text/plain")
        data = await blob_store.get("_health/ping")
        return "ok" if data == b"ok" else "error"
    except Exception:
        return "error"
