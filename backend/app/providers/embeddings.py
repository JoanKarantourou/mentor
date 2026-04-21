import hashlib
import math
import random
from abc import ABC, abstractmethod

from app.config import settings

_STUB_DIMENSION = 1536


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def identifier(self) -> str: ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class StubEmbeddingProvider(EmbeddingProvider):
    @property
    def identifier(self) -> str:
        return "stub-v1"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**32)
            rng = random.Random(seed)
            raw = [rng.gauss(0, 1) for _ in range(_STUB_DIMENSION)]
            norm = math.sqrt(sum(x * x for x in raw)) or 1.0
            vectors.append([x / norm for x in raw])
        return vectors


def get_embedding_provider() -> EmbeddingProvider:
    match settings.EMBEDDING_PROVIDER:
        case "stub":
            return StubEmbeddingProvider()
        case _:
            raise ValueError(f"Unknown embedding provider: {settings.EMBEDDING_PROVIDER!r}")
