import hashlib
import math
import random
from abc import ABC, abstractmethod

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


def get_embedding_provider(settings=None) -> EmbeddingProvider:
    if settings is None:
        from app.config import settings as _settings
        settings = _settings
    match settings.EMBEDDING_PROVIDER:
        case "stub":
            return StubEmbeddingProvider()
        case "azure_openai":
            from app.providers.azure_openai_embeddings import AzureOpenAIEmbeddingProvider

            return AzureOpenAIEmbeddingProvider(
                endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=settings.AZURE_OPENAI_API_KEY.get_secret_value(),
                deployment=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                max_retries=settings.EMBEDDING_MAX_RETRIES,
            )
        case _:
            raise ValueError(f"Unknown embedding provider: {settings.EMBEDDING_PROVIDER!r}")
