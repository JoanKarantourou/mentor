"""Tests for web search providers."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.providers.web_search import StubWebSearchProvider, WebSearchResult, get_web_search_provider


# ---------------------------------------------------------------------------
# StubWebSearchProvider
# ---------------------------------------------------------------------------


async def test_stub_returns_deterministic_results():
    provider = StubWebSearchProvider()
    results = await provider.search("python async generators")
    assert len(results) == 3
    assert all(isinstance(r, WebSearchResult) for r in results)
    # Same query → same results
    results2 = await provider.search("python async generators")
    assert results[0].url == results2[0].url
    assert results[0].title == results2[0].title


async def test_stub_different_queries_give_different_results():
    provider = StubWebSearchProvider()
    r1 = await provider.search("topic A")
    r2 = await provider.search("topic B")
    assert r1[0].url != r2[0].url


async def test_stub_max_results_respected():
    provider = StubWebSearchProvider()
    results = await provider.search("test", max_results=2)
    assert len(results) <= 2


async def test_stub_identifier():
    assert StubWebSearchProvider().identifier == "stub-web-v1"


async def test_stub_result_fields():
    provider = StubWebSearchProvider()
    results = await provider.search("rag pipeline")
    r = results[0]
    assert r.rank == 0
    assert r.title
    assert r.url.startswith("https://")
    assert r.snippet
    assert r.source_domain
    assert r.published_date is not None


# ---------------------------------------------------------------------------
# TavilyWebSearchProvider — mocked at HTTP boundary
# ---------------------------------------------------------------------------


async def test_tavily_happy_path():
    from app.providers.tavily_search import TavilyWebSearchProvider

    mock_response = {
        "results": [
            {
                "title": "RAG Overview",
                "url": "https://example.com/rag",
                "content": "RAG stands for Retrieval Augmented Generation.",
                "published_date": "2026-01-10",
            },
            {
                "title": "Vector Databases",
                "url": "https://vectordb.io/intro",
                "content": "Vector databases store embeddings for fast similarity search.",
                "published_date": None,
            },
        ]
    }

    provider = TavilyWebSearchProvider(api_key="test-key", search_depth="basic")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_response,
            raise_for_status=lambda: None,
        )
        results = await provider.search("what is RAG?", max_results=2)

    assert len(results) == 2
    assert results[0].title == "RAG Overview"
    assert results[0].url == "https://example.com/rag"
    assert results[0].source_domain == "example.com"
    assert results[0].snippet.startswith("RAG stands for")
    assert results[0].published_date == "2026-01-10"
    assert results[0].rank == 0
    assert results[1].published_date is None
    assert results[1].rank == 1


async def test_tavily_identifier():
    from app.providers.tavily_search import TavilyWebSearchProvider

    basic = TavilyWebSearchProvider(api_key="key", search_depth="basic")
    advanced = TavilyWebSearchProvider(api_key="key", search_depth="advanced")
    assert basic.identifier == "tavily-search:basic-v1"
    assert advanced.identifier == "tavily-search:advanced-v1"


async def test_tavily_retries_on_connection_error():
    from app.providers.tavily_search import TavilyWebSearchProvider

    provider = TavilyWebSearchProvider(api_key="test-key")
    call_count = 0

    async def _raise_connect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.ConnectError("Connection refused")
        mock = MagicMock()
        mock.json.return_value = {"results": []}
        mock.raise_for_status = lambda: None
        return mock

    with patch("httpx.AsyncClient.post", new=_raise_connect):
        results = await provider.search("test")
    assert results == []
    assert call_count == 3


async def test_tavily_raises_after_max_retries():
    from app.providers.tavily_search import TavilyWebSearchProvider

    provider = TavilyWebSearchProvider(api_key="test-key")

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("Connection refused"),
    ):
        with pytest.raises(httpx.ConnectError):
            await provider.search("test")


async def test_tavily_retries_on_429():
    from app.providers.tavily_search import TavilyWebSearchProvider

    provider = TavilyWebSearchProvider(api_key="test-key")
    call_count = 0

    async def _rate_limit_then_ok(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            resp = MagicMock()
            resp.status_code = 429
            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "rate limited", request=MagicMock(), response=resp
            )
            return resp
        mock = MagicMock()
        mock.json.return_value = {"results": []}
        mock.raise_for_status = lambda: None
        return mock

    with patch("httpx.AsyncClient.post", new=_rate_limit_then_ok):
        results = await provider.search("test")
    assert results == []
    assert call_count == 2


async def test_tavily_snippet_truncated_to_300():
    from app.providers.tavily_search import TavilyWebSearchProvider

    long_content = "x" * 600
    mock_response = {
        "results": [
            {
                "title": "Test",
                "url": "https://example.com",
                "content": long_content,
                "published_date": None,
            }
        ]
    }

    provider = TavilyWebSearchProvider(api_key="test-key")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_response,
            raise_for_status=lambda: None,
        )
        results = await provider.search("test")

    assert len(results[0].snippet) == 300


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_get_web_search_provider_stub():
    from app.config import Settings

    settings = Settings(WEB_SEARCH_PROVIDER="stub")
    p = get_web_search_provider(settings)
    assert p.identifier == "stub-web-v1"


def test_get_web_search_provider_tavily():
    from app.config import Settings

    settings = Settings(WEB_SEARCH_PROVIDER="tavily", TAVILY_API_KEY="tvly-key")
    p = get_web_search_provider(settings)
    assert "tavily-search" in p.identifier


def test_get_web_search_provider_unknown():
    from app.config import Settings

    with pytest.raises(Exception):
        # Pydantic validation catches unknown literals
        Settings(WEB_SEARCH_PROVIDER="bogus")
