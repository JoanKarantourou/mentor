from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal


@dataclass
class ChatMessage:
    role: Literal["user", "assistant", "system"]
    content: str


@dataclass
class GenerationResult:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: str


class LLMProvider(ABC):
    @property
    @abstractmethod
    def identifier(self) -> str: ...

    @abstractmethod
    async def generate(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> GenerationResult: ...

    @abstractmethod
    async def stream(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]: ...

    def model_for_tier(self, tier: str) -> str | None:
        return None


class StubLLMProvider(LLMProvider):
    @property
    def identifier(self) -> str:
        return "stub-llm-v1"

    async def generate(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> GenerationResult:
        return GenerationResult(
            text="[stub llm response]",
            input_tokens=0,
            output_tokens=0,
            model="stub",
            stop_reason="end_turn",
        )

    async def stream(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        yield "[stub llm response]"


def get_llm_provider(settings=None) -> LLMProvider:
    if settings is None:
        from app.config import settings as _settings
        settings = _settings
    match settings.LLM_PROVIDER:
        case "stub":
            return StubLLMProvider()
        case "anthropic":
            from app.providers.anthropic_llm import AnthropicLLMProvider

            return AnthropicLLMProvider(
                api_key=settings.ANTHROPIC_API_KEY.get_secret_value(),
                default_model=settings.ANTHROPIC_DEFAULT_MODEL,
                strong_model=settings.ANTHROPIC_STRONG_MODEL,
                max_retries=5,
            )
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER!r}")
