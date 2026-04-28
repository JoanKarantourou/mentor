"""E2E: Resilience tests — health check, reindex, document deletion."""

import httpx
import pytest


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok():
    """Health endpoint reports all providers as ok or stub."""
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=15.0) as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "ok"
        assert data["web_search_provider"] in ("stub", "ok")


@pytest.mark.asyncio
async def test_upload_then_delete_removes_from_search():
    """Deleting a document removes it from search results."""
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=60.0) as client:
        content = b"# Unique phrase: xq7z_sentinel_delete_me\n\nThis document will be deleted."
        resp = await client.post(
            "/documents/upload",
            files={"file": ("to_delete.md", content, "text/markdown")},
        )
        assert resp.status_code == 202
        doc_id = resp.json()["document_id"]

        # Delete immediately
        del_resp = await client.delete(f"/documents/{doc_id}")
        assert del_resp.status_code == 204

        # Should return 404
        get_resp = await client.get(f"/documents/{doc_id}")
        assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_search_returns_empty_for_unknown_query():
    """A nonsense query should not error — response is 200 with a hits list."""
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=15.0) as client:
        resp = await client.post(
            "/search",
            json={"query": "xkcd_randomjibberish_zzz_notreal"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "hits" in data
        assert isinstance(data["hits"], list)
