"""E2E: Upload fixture documents and verify they reach 'indexed' status."""

import asyncio
from pathlib import Path

import httpx
import pytest

from e2e.conftest import FIXTURES_DIR, wait_for_document_indexed


@pytest.mark.asyncio
async def test_upload_and_index_fixture_documents():
    """Upload all fixture documents and verify each reaches indexed status."""
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=60.0) as client:
        fixture_files = list(FIXTURES_DIR.glob("*.md"))
        assert len(fixture_files) >= 3, "Need at least 3 fixture files"

        doc_ids = []
        for fixture in fixture_files:
            with open(fixture, "rb") as f:
                resp = await client.post(
                    "/documents/upload",
                    files={"file": (fixture.name, f, "text/markdown")},
                )
            assert resp.status_code == 202, f"Upload failed for {fixture.name}: {resp.text}"
            doc_ids.append(resp.json()["document_id"])

        # Wait for all to index
        docs = await asyncio.gather(
            *[wait_for_document_indexed(client, did) for did in doc_ids]
        )

        for doc, fixture in zip(docs, fixture_files):
            assert doc["status"] == "indexed", (
                f"{fixture.name} reached status {doc['status']}"
            )


@pytest.mark.asyncio
async def test_indexed_documents_appear_in_list():
    """After indexing, documents appear in the listing."""
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        resp = await client.get("/documents")
        assert resp.status_code == 200
        docs = resp.json()
        indexed = [d for d in docs if d["status"] == "indexed"]
        assert len(indexed) >= 1
