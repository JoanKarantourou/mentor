"""E2E test infrastructure — spins up the full stack via docker compose."""

import asyncio
import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest

COMPOSE_FILE = Path(__file__).parent.parent / "docker-compose.yml"
BACKEND_URL = os.environ.get("E2E_BACKEND_URL", "http://localhost:8000")
MAX_WAIT_SECONDS = 120


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)


@pytest.fixture(scope="session", autouse=True)
def docker_stack():
    """Bring up the docker compose stack, yield, then tear down."""
    if os.environ.get("E2E_SKIP_COMPOSE"):
        # Allow running against an already-running stack
        yield
        return

    _run(["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "--build"])
    try:
        _wait_for_health()
        yield
    finally:
        _run(["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"])


def _wait_for_health() -> None:
    deadline = time.time() + MAX_WAIT_SECONDS
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{BACKEND_URL}/health", timeout=5.0)
            if resp.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError(f"Backend did not become healthy within {MAX_WAIT_SECONDS}s")


@pytest.fixture
def client() -> httpx.Client:
    with httpx.Client(base_url=BACKEND_URL, timeout=30.0) as c:
        yield c


@pytest.fixture
def async_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BACKEND_URL, timeout=30.0)


async def wait_for_document_indexed(client: httpx.AsyncClient, doc_id: str, timeout: float = 60.0) -> dict:
    """Poll until a document reaches 'indexed' or 'error' status."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/documents/{doc_id}")
        resp.raise_for_status()
        doc = resp.json()
        if doc["status"] in ("indexed", "error", "failed"):
            return doc
        await asyncio.sleep(1.0)
    raise TimeoutError(f"Document {doc_id} did not reach terminal status in {timeout}s")


FIXTURES_DIR = Path(__file__).parent / "fixtures"
