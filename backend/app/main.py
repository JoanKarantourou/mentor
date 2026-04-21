import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.search import router as search_router
from app.config import settings
from app.db import engine, make_session_factory
from app.ingestion.pipeline import IngestionPipeline
from app.providers.embeddings import get_embedding_provider
from app.storage.factory import create_blob_store

logging.basicConfig(level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    blob_store = create_blob_store()
    sf = make_session_factory(engine)
    embedding_provider = get_embedding_provider()
    app.state.blob_store = blob_store
    app.state.session_factory = sf
    app.state.embedding_provider = embedding_provider
    app.state.pipeline = IngestionPipeline(
        session_factory=sf,
        blob_store=blob_store,
        embedding_provider=embedding_provider,
    )
    yield


app = FastAPI(title="mentor", version="0.3.0", lifespan=lifespan)

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
