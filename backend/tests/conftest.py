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
from app.models import Chunk, Document  # noqa: F401 — registers tables in SQLModel.metadata
from app.providers.embeddings import StubEmbeddingProvider
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


# ---------------------------------------------------------------------------
# Session-scoped: create the test database and schema once per pytest session
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Function-scoped: truncate tables between tests for isolation
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(test_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    yield
    async with test_engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE documents CASCADE"))


# ---------------------------------------------------------------------------
# Per-test DB session
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(test_engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Per-test blob store backed by pytest tmp_path
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_blob_store(tmp_path: Path) -> LocalBlobStore:
    return LocalBlobStore(root=tmp_path / "blobs")


# ---------------------------------------------------------------------------
# HTTP test client with overridden state and dependencies
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client(
    test_engine: AsyncEngine,
    tmp_blob_store: LocalBlobStore,
) -> AsyncGenerator[AsyncClient, None]:
    from app.main import app

    sf = make_session_factory(test_engine)
    embedding_provider = StubEmbeddingProvider()
    pipeline = IngestionPipeline(
        session_factory=sf,
        blob_store=tmp_blob_store,
        embedding_provider=embedding_provider,
    )
    app.state.blob_store = tmp_blob_store
    app.state.pipeline = pipeline
    app.state.session_factory = sf
    app.state.embedding_provider = embedding_provider

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
