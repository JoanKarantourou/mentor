from abc import ABC, abstractmethod

from app.config import settings


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict], model: str | None = None) -> str: ...


class StubLLMProvider(LLMProvider):
    async def generate(self, messages: list[dict], model: str | None = None) -> str:
        return "[stub llm response]"


def get_llm_provider() -> LLMProvider:
    match settings.LLM_PROVIDER:
        case "stub":
            return StubLLMProvider()
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER!r}")
