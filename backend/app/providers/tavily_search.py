from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx
import tenacity

from app.providers.web_search import WebSearchProvider, WebSearchResult

logger = logging.getLogger(__name__)


class TavilyWebSearchProvider(WebSearchProvider):
    _ENDPOINT = "https://api.tavily.com/search"

    def __init__(self, api_key: str, search_depth: str = "basic") -> None:
        self._api_key = api_key
        self._search_depth = search_depth

    @property
    def identifier(self) -> str:
        return f"tavily-search:{self._search_depth}-v1"

    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        api_key = self._api_key
        depth = self._search_depth
        endpoint = self._ENDPOINT

        @tenacity.retry(
            retry=tenacity.retry_if_exception(
                lambda exc: (
                    isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))
                    or (
                        isinstance(exc, httpx.HTTPStatusError)
                        and exc.response.status_code in (429, 500, 502, 503, 504)
                    )
                )
            ),
            wait=tenacity.wait_exponential(multiplier=1.0, min=1.0, max=8.0),
            stop=tenacity.stop_after_attempt(3),
            reraise=True,
        )
        async def _call() -> list[WebSearchResult]:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    endpoint,
                    json={
                        "api_key": api_key,
                        "query": query,
                        "search_depth": depth,
                        "max_results": max_results,
                        "include_answer": False,
                        "include_raw_content": False,
                    },
                )
                response.raise_for_status()
                data = response.json()

            results = []
            for i, item in enumerate(data.get("results", [])):
                snippet = (item.get("content") or "")[:300]
                url = item.get("url", "")
                source_domain = urlparse(url).netloc or url
                results.append(
                    WebSearchResult(
                        title=item.get("title", ""),
                        url=url,
                        snippet=snippet,
                        published_date=item.get("published_date"),
                        source_domain=source_domain,
                        rank=i,
                    )
                )
            return results

        return await _call()
