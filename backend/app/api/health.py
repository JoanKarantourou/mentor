import asyncio

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.db import engine
from app.providers.llm import ChatMessage

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    db_status = await _check_db()
    blob_status = await _check_blob_store(request)
    vector_index_status = await _check_vector_index()
    embedding_status = await _check_embedding_provider(request)
    llm_status = await _check_llm_provider(request)
    web_search_status = await _check_web_search_provider(request)
    return {
        "status": "ok",
        "database": db_status,
        "blob_store": blob_status,
        "vector_index": vector_index_status,
        "embedding_provider": embedding_status,
        "llm_provider": llm_status,
        "web_search_provider": web_search_status,
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


async def _check_vector_index() -> str:
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT 1 FROM pg_indexes "
                    "WHERE tablename = 'chunks' AND indexname = 'ix_chunks_embedding_hnsw'"
                )
            )
            return "ok" if result.first() else "missing"
    except Exception:
        return "error"


async def _check_embedding_provider(request: Request) -> str:
    provider = getattr(request.app.state, "embedding_provider", None)
    if provider is None:
        return "not configured"
    if provider.identifier == "stub-v1":
        return "stub"
    try:
        async with asyncio.timeout(5.0):
            await provider.embed(["healthcheck"])
        return "ok"
    except Exception as exc:
        brief = str(exc)[:120]
        return f"error: {brief}"


async def _check_llm_provider(request: Request) -> str:
    provider = getattr(request.app.state, "llm_provider", None)
    if provider is None:
        return "not configured"
    if provider.identifier == "stub-llm-v1":
        return "stub"
    try:
        async with asyncio.timeout(10.0):
            await provider.generate(
                messages=[ChatMessage(role="user", content="ping")],
                system_prompt="Reply with one word.",
                max_tokens=5,
            )
        return "ok"
    except Exception as exc:
        brief = str(exc)[:120]
        return f"error: {brief}"


async def _check_web_search_provider(request: Request) -> str:
    provider = getattr(request.app.state, "web_search_provider", None)
    if provider is None:
        return "not configured"
    if provider.identifier == "stub-web-v1":
        return "stub"
    try:
        async with asyncio.timeout(5.0):
            await provider.search("healthcheck", max_results=1)
        return "ok"
    except Exception as exc:
        brief = str(exc)[:120]
        return f"error: {brief}"
