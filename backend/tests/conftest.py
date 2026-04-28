import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session, make_session_factory
from app.ingestion.pipeline import IngestionPipeline
from app.models import Chunk, Conversation, Document, Message  # noqa: F401
from app.providers.embeddings import StubEmbeddingProvider
from app.providers.llm import StubLLMProvider
from app.providers.web_search import StubWebSearchProvider
from app.storage.local import LocalBlobStore

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/mentor_test",
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_pdf_bytes() -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=14)
    from fpdf.enums import XPos, YPos

    pdf.cell(0, 10, "Introduction to Machine Learning", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", size=12)
    lines = [
        "Machine learning is a branch of artificial intelligence.",
        "It enables systems to learn from experience without explicit programming.",
        "Supervised learning uses labeled datasets to train models.",
        "Common applications include image recognition and natural language processing.",
    ]
    for line in lines:
        pdf.cell(0, 8, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    admin_url = TEST_DB_URL.rsplit("/", 1)[0] + "/postgres"
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        exists = (
            await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = 'mentor_test'")
            )
        ).first()
        if not exists:
            await conn.execute(text("CREATE DATABASE mentor_test"))
    await admin.dispose()

    eng = create_async_engine(TEST_DB_URL)
    async with eng.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(test_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    yield
    async with test_engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE documents, conversations CASCADE"))


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(test_engine) as session:
        yield session


@pytest.fixture
def tmp_blob_store(tmp_path: Path) -> LocalBlobStore:
    return LocalBlobStore(root=tmp_path / "blobs")


@pytest_asyncio.fixture
async def async_client(
    test_engine: AsyncEngine,
    tmp_blob_store: LocalBlobStore,
) -> AsyncGenerator[AsyncClient, None]:
    from app.config import settings
    from app.main import app

    sf = make_session_factory(test_engine)
    embedding_provider = StubEmbeddingProvider()
    llm_provider = StubLLMProvider()
    web_search_provider = StubWebSearchProvider()
    pipeline = IngestionPipeline(
        session_factory=sf,
        blob_store=tmp_blob_store,
        embedding_provider=embedding_provider,
    )
    app.state.blob_store = tmp_blob_store
    app.state.pipeline = pipeline
    app.state.session_factory = sf
    app.state.embedding_provider = embedding_provider
    app.state.llm_provider = llm_provider
    app.state.web_search_provider = web_search_provider
    app.state.chat_config = {
        "top_k": settings.RETRIEVAL_TOP_K,
        "min_top_similarity": settings.RETRIEVAL_MIN_TOP_SIMILARITY,
        "min_avg_similarity": settings.RETRIEVAL_MIN_AVG_SIMILARITY,
        "avg_window": settings.RETRIEVAL_AVG_WINDOW,
        "max_context_chunks": settings.CHAT_MAX_CONTEXT_CHUNKS,
        "max_output_tokens": settings.CHAT_MAX_OUTPUT_TOKENS,
        "web_search_max_results": settings.WEB_SEARCH_MAX_RESULTS,
    }

    async def _override_session():
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = _override_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()
