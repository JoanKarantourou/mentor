from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class WebSearchResult:
    title: str
    url: str
    snippet: str
    published_date: str | None
    source_domain: str
    rank: int


class WebSearchProvider(ABC):
    @property
    @abstractmethod
    def identifier(self) -> str: ...

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]: ...


class StubWebSearchProvider(WebSearchProvider):
    """Deterministic fake results keyed on query hash — for tests and stub mode."""

    @property
    def identifier(self) -> str:
        return "stub-web-v1"

    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        seed = int(hashlib.md5(query.encode()).hexdigest(), 16)
        topics = [
            ("architecture", "docs.example.com"),
            ("tutorial", "guide.example.org"),
            ("api-reference", "api.example.io"),
        ]
        results = []
        for i in range(min(3, max_results)):
            topic, domain = topics[i % len(topics)]
            h = (seed + i * 1337) % 10**9
            results.append(
                WebSearchResult(
                    title=f"Understanding {query[:40]} — {topic.replace('-', ' ').title()}",
                    url=f"https://{domain}/{topic}/{h:08x}",
                    snippet=(
                        f"This article covers {query[:80]}. "
                        "Key concepts include the foundational patterns and best practices "
                        "for implementing robust solutions in modern systems."
                    ),
                    published_date="2026-01-15",
                    source_domain=domain,
                    rank=i,
                )
            )
        return results


def get_web_search_provider(settings=None) -> WebSearchProvider:
    if settings is None:
        from app.config import settings as _settings
        settings = _settings
    match settings.WEB_SEARCH_PROVIDER:
        case "stub":
            return StubWebSearchProvider()
        case "tavily":
            from app.providers.tavily_search import TavilyWebSearchProvider
            return TavilyWebSearchProvider(
                api_key=settings.TAVILY_API_KEY.get_secret_value(),
                search_depth=settings.TAVILY_SEARCH_DEPTH,
            )
        case _:
            raise ValueError(f"Unknown web search provider: {settings.WEB_SEARCH_PROVIDER!r}")
