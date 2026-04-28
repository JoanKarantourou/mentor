import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.chat import router as chat_router
from app.api.curation import router as curation_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.search import router as search_router
from app.config import settings
from app.db import engine, make_session_factory
from app.ingestion.pipeline import IngestionPipeline
from app.providers.embeddings import get_embedding_provider
from app.providers.llm import get_llm_provider
from app.providers.web_search import get_web_search_provider
from app.storage.factory import create_blob_store

logging.basicConfig(level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    blob_store = create_blob_store()
    sf = make_session_factory(engine)
    embedding_provider = get_embedding_provider()
    llm_provider = get_llm_provider()
    web_search_provider = get_web_search_provider()
    app.state.blob_store = blob_store
    app.state.session_factory = sf
    app.state.embedding_provider = embedding_provider
    app.state.llm_provider = llm_provider
    app.state.web_search_provider = web_search_provider
    app.state.pipeline = IngestionPipeline(
        session_factory=sf,
        blob_store=blob_store,
        embedding_provider=embedding_provider,
        duplicate_detection_enabled=settings.DUPLICATE_DETECTION_ENABLED,
        duplicate_near_threshold=settings.DUPLICATE_NEAR_THRESHOLD,
        duplicate_match_ratio=settings.DUPLICATE_MATCH_RATIO,
    )
    app.state.chat_config = {
        "top_k": settings.RETRIEVAL_TOP_K,
        "min_top_similarity": settings.RETRIEVAL_MIN_TOP_SIMILARITY,
        "min_avg_similarity": settings.RETRIEVAL_MIN_AVG_SIMILARITY,
        "avg_window": settings.RETRIEVAL_AVG_WINDOW,
        "max_context_chunks": settings.CHAT_MAX_CONTEXT_CHUNKS,
        "max_output_tokens": settings.CHAT_MAX_OUTPUT_TOKENS,
        "web_search_max_results": settings.WEB_SEARCH_MAX_RESULTS,
        "gap_analysis_enabled": settings.GAP_ANALYSIS_ENABLED,
        "memory_extraction_min_messages": settings.MEMORY_EXTRACTION_MIN_MESSAGES,
        "memory_extraction_topic_shift_threshold": settings.MEMORY_EXTRACTION_TOPIC_SHIFT_THRESHOLD,
        "memory_extraction_session_break_minutes": settings.MEMORY_EXTRACTION_SESSION_BREAK_MINUTES,
    }
    yield


app = FastAPI(title="mentor", version="0.5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "dev" else [],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(admin_router)
app.include_router(chat_router)
app.include_router(curation_router)
