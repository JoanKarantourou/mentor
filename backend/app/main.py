import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.search import router as search_router
from app.config import settings
from app.db import engine, make_session_factory
from app.ingestion.pipeline import IngestionPipeline
from app.providers.embeddings import get_embedding_provider
from app.providers.llm import get_llm_provider
from app.storage.factory import create_blob_store

logging.basicConfig(level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    blob_store = create_blob_store()
    sf = make_session_factory(engine)
    embedding_provider = get_embedding_provider()
    llm_provider = get_llm_provider()
    app.state.blob_store = blob_store
    app.state.session_factory = sf
    app.state.embedding_provider = embedding_provider
    app.state.llm_provider = llm_provider
    app.state.pipeline = IngestionPipeline(
        session_factory=sf,
        blob_store=blob_store,
        embedding_provider=embedding_provider,
    )
    app.state.chat_config = {
        "top_k": settings.RETRIEVAL_TOP_K,
        "min_top_similarity": settings.RETRIEVAL_MIN_TOP_SIMILARITY,
        "min_avg_similarity": settings.RETRIEVAL_MIN_AVG_SIMILARITY,
        "avg_window": settings.RETRIEVAL_AVG_WINDOW,
        "max_context_chunks": settings.CHAT_MAX_CONTEXT_CHUNKS,
        "max_output_tokens": settings.CHAT_MAX_OUTPUT_TOKENS,
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
