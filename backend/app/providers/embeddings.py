from abc import ABC, abstractmethod

from app.config import settings

_STUB_DIMENSION = 1536


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class StubEmbeddingProvider(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * _STUB_DIMENSION
            vec[hash(text) % _STUB_DIMENSION] = 1.0
            vectors.append(vec)
        return vectors


def get_embedding_provider() -> EmbeddingProvider:
    match settings.EMBEDDING_PROVIDER:
        case "stub":
            return StubEmbeddingProvider()
        case _:
            raise ValueError(f"Unknown embedding provider: {settings.EMBEDDING_PROVIDER!r}")
