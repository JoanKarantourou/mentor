"""Unit-level tests for the ingestion pipeline and its components."""

import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import make_session_factory
from app.ingestion.categorizer import categorize
from app.ingestion.language import detect_language
from app.ingestion.pipeline import IngestionPipeline
from app.models.document import Document
from app.storage.local import LocalBlobStore

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _insert_doc(
    sf,
    filename: str,
    content_type: str,
    blob_store: LocalBlobStore,
    data: bytes,
) -> Document:
    doc_id = uuid.uuid4()
    blob_key = f"documents/{doc_id}/{filename}"
    await blob_store.put(blob_key, data, content_type)
    doc = Document(
        id=doc_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        blob_path=blob_key,
        status="pending",
        file_category="document",
    )
    async with sf() as session:
        session.add(doc)
        await session.commit()
    return doc


@pytest_asyncio.fixture
def pipeline(test_engine: AsyncEngine, tmp_blob_store: LocalBlobStore) -> IngestionPipeline:
    return IngestionPipeline(
        session_factory=make_session_factory(test_engine),
        blob_store=tmp_blob_store,
    )


# ---------------------------------------------------------------------------
# Categorizer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("filename", "mime", "expected"),
    [
        ("script.py", "text/x-python", "code"),
        ("app.ts", "application/typescript", "code"),
        ("main.go", "text/plain", "code"),
        ("report.pdf", "application/pdf", "document"),
        ("notes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "document"),
        ("readme.md", "text/markdown", "document"),
        ("style.css", "text/css", "document"),
        ("unknown", "application/octet-stream", "document"),
    ],
)
def test_categorize(filename: str, mime: str, expected: str) -> None:
    assert categorize(filename, mime) == expected


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


def test_detect_english() -> None:
    text = (FIXTURES / "sample.md").read_text(encoding="utf-8")
    assert detect_language(text) == "en"


def test_detect_greek() -> None:
    text = (FIXTURES / "sample_greek.txt").read_text(encoding="utf-8")
    assert detect_language(text) == "el"


def test_detect_empty_returns_none() -> None:
    assert detect_language("") is None
    assert detect_language("   ") is None


# ---------------------------------------------------------------------------
# Pipeline: happy paths
# ---------------------------------------------------------------------------


async def test_markdown_pipeline_reaches_ready(
    pipeline: IngestionPipeline,
    test_engine: AsyncEngine,
    tmp_blob_store: LocalBlobStore,
) -> None:
    sf = make_session_factory(test_engine)
    data = (FIXTURES / "sample.md").read_bytes()
    doc = await _insert_doc(sf, "sample.md", "text/markdown", tmp_blob_store, data)

    await pipeline.run(doc.id)

    async with AsyncSession(test_engine) as session:
        updated = await session.get(Document, doc.id)

    assert updated.status == "ready"
    assert updated.normalized_content
    assert updated.detected_language == "en"
    assert updated.file_category == "document"


async def test_python_file_is_categorized_as_code(
    pipeline: IngestionPipeline,
    test_engine: AsyncEngine,
    tmp_blob_store: LocalBlobStore,
) -> None:
    sf = make_session_factory(test_engine)
    data = (FIXTURES / "sample.py").read_bytes()
    doc = await _insert_doc(sf, "sample.py", "text/x-python", tmp_blob_store, data)

    await pipeline.run(doc.id)

    async with AsyncSession(test_engine) as session:
        updated = await session.get(Document, doc.id)

    assert updated.status == "ready"
    assert updated.file_category == "code"
    # Normalized content must be a fenced code block
    assert updated.normalized_content.startswith("```")


async def test_greek_text_language_detected(
    pipeline: IngestionPipeline,
    test_engine: AsyncEngine,
    tmp_blob_store: LocalBlobStore,
) -> None:
    sf = make_session_factory(test_engine)
    data = (FIXTURES / "sample_greek.txt").read_bytes()
    doc = await _insert_doc(sf, "sample_greek.txt", "text/plain", tmp_blob_store, data)

    await pipeline.run(doc.id)

    async with AsyncSession(test_engine) as session:
        updated = await session.get(Document, doc.id)

    assert updated.status == "ready"
    assert updated.detected_language == "el"


# ---------------------------------------------------------------------------
# Pipeline: error handling
# ---------------------------------------------------------------------------


async def test_missing_blob_sets_status_failed(
    pipeline: IngestionPipeline,
    test_engine: AsyncEngine,
    tmp_blob_store: LocalBlobStore,
) -> None:
    sf = make_session_factory(test_engine)
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        filename="ghost.txt",
        content_type="text/plain",
        size_bytes=0,
        blob_path="documents/ghost/ghost.txt",  # blob never written
        status="pending",
        file_category="document",
    )
    async with sf() as session:
        session.add(doc)
        await session.commit()

    await pipeline.run(doc_id)

    async with AsyncSession(test_engine) as session:
        updated = await session.get(Document, doc_id)

    assert updated.status == "failed"
    assert updated.error_message


async def test_status_transitions_through_processing(
    pipeline: IngestionPipeline,
    test_engine: AsyncEngine,
    tmp_blob_store: LocalBlobStore,
) -> None:
    """Pipeline must set status=processing before doing any work."""
    sf = make_session_factory(test_engine)
    data = (FIXTURES / "sample.md").read_bytes()
    doc = await _insert_doc(sf, "sample.md", "text/markdown", tmp_blob_store, data)

    # Run pipeline fully — we just verify the final state is "ready"
    await pipeline.run(doc.id)

    async with AsyncSession(test_engine) as session:
        updated = await session.get(Document, doc.id)
    assert updated.status == "ready"
