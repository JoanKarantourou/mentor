import logging
import time
from collections.abc import AsyncIterator

import tenacity
from anthropic import APIConnectionError, APITimeoutError, AsyncAnthropic, RateLimitError

from app.providers.llm import ChatMessage, GenerationResult, LLMProvider

logger = logging.getLogger(__name__)


class AnthropicLLMProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        default_model: str = "claude-haiku-4-5",
        strong_model: str = "claude-sonnet-4-5",
        max_retries: int = 5,
    ) -> None:
        self._default_model = default_model
        self._strong_model = strong_model
        self._max_retries = max_retries
        # max_retries=0 disables the SDK's built-in retry so tenacity has full control.
        self._client = AsyncAnthropic(api_key=api_key, max_retries=0)

    @property
    def identifier(self) -> str:
        return f"anthropic:{self._default_model}:v1"

    def model_for_tier(self, tier: str) -> str | None:
        if tier == "strong":
            return self._strong_model
        return None

    async def generate(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> GenerationResult:
        model = model or self._default_model
        api_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]
        start = time.monotonic()
        result = await self._generate_with_retry(api_messages, system_prompt, model, max_tokens, temperature)
        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "generate model=%s input_tokens=%d output_tokens=%d duration_ms=%.0f stop_reason=%s",
            result.model,
            result.input_tokens,
            result.output_tokens,
            duration_ms,
            result.stop_reason,
        )
        return result

    async def stream(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        model = model or self._default_model
        api_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]
        start = time.monotonic()
        token_count = 0
        async with self._client.messages.stream(
            model=model,
            system=system_prompt,
            messages=api_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        ) as stream:
            async for text in stream.text_stream:
                token_count += 1
                yield text
            final = await stream.get_final_message()
        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "stream model=%s input_tokens=%d output_tokens=%d duration_ms=%.0f",
            model,
            final.usage.input_tokens,
            final.usage.output_tokens,
            duration_ms,
        )

    async def _generate_with_retry(
        self,
        api_messages: list[dict],
        system_prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> GenerationResult:
        max_retries = self._max_retries
        client = self._client

        @tenacity.retry(
            retry=tenacity.retry_if_exception_type(
                (APIConnectionError, APITimeoutError, RateLimitError)
            ),
            wait=_retry_wait,
            stop=tenacity.stop_after_attempt(max_retries),
            reraise=True,
        )
        async def _call() -> GenerationResult:
            response = await client.messages.create(
                model=model,
                system=system_prompt,
                messages=api_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = response.content[0].text if response.content else ""
            return GenerationResult(
                text=text,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=response.model,
                stop_reason=response.stop_reason or "end_turn",
            )

        return await _call()


def _retry_wait(retry_state: tenacity.RetryCallState) -> float:
    exc = retry_state.outcome.exception()
    if isinstance(exc, RateLimitError) and exc.response is not None:
        retry_after = exc.response.headers.get("retry-after")
        if retry_after:
            try:
                return float(retry_after)
            except (ValueError, TypeError):
                pass
    return min(2.0 ** retry_state.attempt_number, 60.0)
