"""Ingestion edge cases: malformed input, size limits, multi-language, concurrent uploads."""

import asyncio
import io
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.document import Document


# ---------------------------------------------------------------------------
# 0-byte file
# ---------------------------------------------------------------------------


async def test_upload_zero_byte_file_fails_gracefully(async_client: AsyncClient) -> None:
    empty = io.BytesIO(b"")
    resp = await async_client.post(
        "/documents/upload",
        files={"file": ("empty.md", empty, "text/markdown")},
    )
    # Either 400/422 or the pipeline marks the document as failed
    if resp.status_code == 202:
        # Accepted but ingestion should fail
        doc_id = resp.json()["document_id"]
        # The document will either stay pending or go to error state — not indexed
        get_resp = await async_client.get(f"/documents/{doc_id}")
        if get_resp.status_code == 200:
            status = get_resp.json()["status"]
            assert status in ("pending", "error", "failed")
    else:
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# File too large
# ---------------------------------------------------------------------------


async def test_upload_file_exceeds_size_limit(async_client: AsyncClient) -> None:
    # We patch the settings to a very small limit
    with patch("app.api.documents.settings") as mock_settings:
        mock_settings.MAX_UPLOAD_SIZE_BYTES = 10  # 10 bytes
        large = io.BytesIO(b"x" * 100)
        resp = await async_client.post(
            "/documents/upload",
            files={"file": ("big.md", large, "text/markdown")},
        )
    assert resp.status_code == 413


# ---------------------------------------------------------------------------
# Deceptive extension (text content with .pdf extension)
# ---------------------------------------------------------------------------


async def test_upload_deceptive_extension(
    async_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    fake_pdf = io.BytesIO(b"This is just plain text, not a PDF at all.")
    resp = await async_client.post(
        "/documents/upload",
        files={"file": ("trick.pdf", fake_pdf, "application/pdf")},
    )
    # Should be accepted (202) but the ingestion pipeline may fail or succeed
    # depending on unstructured's tolerance — the key thing is it doesn't crash
    assert resp.status_code in (202, 400, 415, 422)


# ---------------------------------------------------------------------------
# Non-Latin characters (Greek text)
# ---------------------------------------------------------------------------


async def test_upload_greek_text_document(
    async_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    greek_text = (
        "# Αρχιτεκτονική Συστήματος\n\n"
        "Το σύστημα χρησιμοποιεί τη γλώσσα Python για την υλοποίησή του.\n\n"
        "## Κύρια Χαρακτηριστικά\n\n"
        "- Ταχύτητα και αξιοπιστία\n"
        "- Ευκολία χρήσης\n"
        "- Επεκτασιμότητα\n"
    )
    data = io.BytesIO(greek_text.encode("utf-8"))
    resp = await async_client.post(
        "/documents/upload",
        files={"file": ("greek.md", data, "text/markdown")},
    )
    assert resp.status_code == 202
    doc_id = resp.json()["document_id"]

    get_resp = await async_client.get(f"/documents/{doc_id}")
    assert get_resp.status_code == 200
    data_json = get_resp.json()
    assert data_json["id"] == doc_id


# ---------------------------------------------------------------------------
# Concurrent uploads of the same filename
# ---------------------------------------------------------------------------


async def test_concurrent_uploads_same_filename(
    async_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    content = b"# Concurrent Test\n\nSome content here."

    async def upload():
        f = io.BytesIO(content)
        return await async_client.post(
            "/documents/upload",
            files={"file": ("concurrent.md", f, "text/markdown")},
        )

    resp1, resp2 = await asyncio.gather(upload(), upload())
    assert resp1.status_code == 202
    assert resp2.status_code == 202
    id1 = resp1.json()["document_id"]
    id2 = resp2.json()["document_id"]
    assert id1 != id2, "Concurrent uploads must get distinct IDs"


# ---------------------------------------------------------------------------
# Markdown with deeply nested headings
# ---------------------------------------------------------------------------


async def test_upload_deeply_nested_markdown(
    async_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    content = "\n\n".join(
        [
            f"{'#' * level} Heading Level {level}\n\nContent for level {level}."
            for level in range(1, 7)
        ]
    )
    data = io.BytesIO(content.encode())
    resp = await async_client.post(
        "/documents/upload",
        files={"file": ("nested.md", data, "text/markdown")},
    )
    assert resp.status_code == 202


# ---------------------------------------------------------------------------
# Unsupported language file falls back to plain chunking
# ---------------------------------------------------------------------------


async def test_upload_haskell_file(
    async_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    haskell_code = (
        "module Main where\n\n"
        "import Data.List (sort)\n\n"
        "main :: IO ()\n"
        "main = do\n"
        "    let xs = [3, 1, 4, 1, 5, 9, 2, 6]\n"
        "    print (sort xs)\n\n"
        "factorial :: Integer -> Integer\n"
        "factorial 0 = 1\n"
        "factorial n = n * factorial (n - 1)\n"
    )
    data = io.BytesIO(haskell_code.encode())
    resp = await async_client.post(
        "/documents/upload",
        files={"file": ("main.hs", data, "text/plain")},
    )
    assert resp.status_code == 202


# ---------------------------------------------------------------------------
# Lua file (another unsupported language)
# ---------------------------------------------------------------------------


async def test_upload_lua_file(
    async_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    lua_code = (
        "-- Lua script\n"
        "local function greet(name)\n"
        "    print('Hello, ' .. name .. '!')\n"
        "end\n\n"
        "greet('World')\n"
    )
    data = io.BytesIO(lua_code.encode())
    resp = await async_client.post(
        "/documents/upload",
        files={"file": ("script.lua", data, "text/plain")},
    )
    assert resp.status_code == 202
