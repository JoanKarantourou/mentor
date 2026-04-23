import logging
import time

import tenacity
import tiktoken
from openai import APIConnectionError, APITimeoutError, AsyncAzureOpenAI, RateLimitError

from app.providers.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)

_TOKENIZER = tiktoken.get_encoding("cl100k_base")
_MAX_TOKENS = 8000  # conservative margin under the hard 8191-token limit


class AzureOpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str,
        max_retries: int = 5,
    ) -> None:
        self._deployment = deployment
        self._max_retries = max_retries
        # max_retries=0 disables the SDK's built-in retry so tenacity has full control.
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            max_retries=0,
        )

    @property
    def identifier(self) -> str:
        return f"azure-openai:{self._deployment}:v1"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        truncated = self._truncate(texts)
        token_count = sum(len(_TOKENIZER.encode(t)) for t in truncated)
        start = time.monotonic()
        vectors = await self._embed_with_retry(truncated)
        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "embed texts=%d tokens=%d duration_ms=%.0f provider=%s",
            len(texts),
            token_count,
            duration_ms,
            self.identifier,
        )
        return vectors

    def _truncate(self, texts: list[str]) -> list[str]:
        result = []
        for text in texts:
            tokens = _TOKENIZER.encode(text)
            if len(tokens) > _MAX_TOKENS:
                logger.warning(
                    "Input truncated: %d tokens → %d (provider=%s)",
                    len(tokens),
                    _MAX_TOKENS,
                    self.identifier,
                )
                text = _TOKENIZER.decode(tokens[:_MAX_TOKENS])
            result.append(text)
        return result

    async def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        max_retries = self._max_retries
        client = self._client
        deployment = self._deployment

        @tenacity.retry(
            retry=tenacity.retry_if_exception_type(
                (APIConnectionError, APITimeoutError, RateLimitError)
            ),
            wait=_retry_wait,
            stop=tenacity.stop_after_attempt(max_retries),
            reraise=True,
        )
        async def _call() -> list[list[float]]:
            response = await client.embeddings.create(input=texts, model=deployment)
            for i, item in enumerate(response.data):
                assert item.index == i, (
                    f"Unexpected response ordering: expected index {i}, got {item.index}"
                )
            return [item.embedding for item in response.data]

        return await _call()


def _retry_wait(retry_state: tenacity.RetryCallState) -> float:
    """Respect Retry-After header from 429s; fall back to exponential backoff."""
    exc = retry_state.outcome.exception()
    if isinstance(exc, RateLimitError) and exc.response is not None:
        retry_after = exc.response.headers.get("retry-after")
        if retry_after:
            try:
                return float(retry_after)
            except (ValueError, TypeError):
                pass
    return min(2.0 ** retry_state.attempt_number, 60.0)
