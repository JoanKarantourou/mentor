"""Tests for OpenAIEmbeddingProvider.

No real OpenAI API calls are made here. All network I/O is mocked at the
AsyncOpenAI client layer.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import APIConnectionError, RateLimitError

from app.providers.embeddings import get_embedding_provider
from app.providers.openai_embeddings import OpenAIEmbeddingProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(max_retries: int = 5) -> OpenAIEmbeddingProvider:
    return OpenAIEmbeddingProvider(
        api_key="test-key",
        model="text-embedding-3-small",
        max_retries=max_retries,
    )


def _make_embed_response(vectors: list[list[float]], shuffle: bool = False) -> MagicMock:
    """Build a mock response matching openai EmbeddingCreateResponse structure."""
    response = MagicMock()
    items = []
    indices = list(range(len(vectors)))
    if shuffle and len(indices) > 1:
        indices[0], indices[1] = indices[1], indices[0]
    for i, vec in enumerate(vectors):
        item = MagicMock()
        item.index = indices[i]
        item.embedding = vec
        items.append(item)
    response.data = items
    return response


def _make_rate_limit_error(retry_after: str | None = None) -> RateLimitError:
    headers = {"retry-after": retry_after} if retry_after else {}
    response = httpx.Response(
        429,
        headers=headers,
        request=httpx.Request("POST", "https://api.openai.com"),
    )
    return RateLimitError("Rate limit exceeded", response=response, body=None)


def _make_connection_error() -> APIConnectionError:
    return APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))


# ---------------------------------------------------------------------------
# Settings validation
# ---------------------------------------------------------------------------


def test_settings_validation_raises_when_openai_key_missing() -> None:
    """Settings must reject openai provider without OPENAI_API_KEY."""
    import os
    from unittest.mock import patch
    from pydantic import ValidationError
    from app.config import Settings

    # OPENAI_API_KEY may be present in the real environment; strip it for this test
    # and skip reading the .env file so the validator sees a genuinely missing key.
    with patch.dict(os.environ, {}, clear=False) as patched_env:
        patched_env.pop("OPENAI_API_KEY", None)
        with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
            Settings(EMBEDDING_PROVIDER="openai", _env_file=None)


def test_settings_validation_passes_with_api_key() -> None:
    from app.config import Settings

    s = Settings(EMBEDDING_PROVIDER="openai", OPENAI_API_KEY="sk-test")
    assert s.EMBEDDING_PROVIDER == "openai"


def test_factory_returns_openai_provider() -> None:
    from app.config import Settings

    s = Settings(EMBEDDING_PROVIDER="openai", OPENAI_API_KEY="sk-test")
    provider = get_embedding_provider(s)
    assert isinstance(provider, OpenAIEmbeddingProvider)


# ---------------------------------------------------------------------------
# identifier
# ---------------------------------------------------------------------------


def test_identifier_format() -> None:
    provider = _make_provider()
    assert provider.identifier == "openai:text-embedding-3-small:v1"


# ---------------------------------------------------------------------------
# embed() happy path
# ---------------------------------------------------------------------------


async def test_embed_happy_path() -> None:
    provider = _make_provider()
    vectors = [[0.1] * 1536, [0.2] * 1536]
    mock_response = _make_embed_response(vectors)

    with patch.object(provider._client.embeddings, "create", new=AsyncMock(return_value=mock_response)):
        result = await provider.embed(["hello", "world"])

    assert len(result) == 2
    assert result[0] == [0.1] * 1536
    assert result[1] == [0.2] * 1536


async def test_embed_single_text() -> None:
    provider = _make_provider()
    mock_response = _make_embed_response([[0.5] * 1536])

    with patch.object(provider._client.embeddings, "create", new=AsyncMock(return_value=mock_response)):
        result = await provider.embed(["single input"])

    assert len(result) == 1
    assert len(result[0]) == 1536


async def test_embed_passes_model_name_directly() -> None:
    provider = _make_provider()
    mock_create = AsyncMock(return_value=_make_embed_response([[0.1] * 1536]))

    with patch.object(provider._client.embeddings, "create", new=mock_create):
        await provider.embed(["test"])

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["model"] == "text-embedding-3-small"


# ---------------------------------------------------------------------------
# Retry: success after 429
# ---------------------------------------------------------------------------


async def test_retry_succeeds_after_429() -> None:
    provider = _make_provider(max_retries=3)
    good_response = _make_embed_response([[0.3] * 1536])
    mock_create = AsyncMock(side_effect=[_make_rate_limit_error(), good_response])

    with (
        patch.object(provider._client.embeddings, "create", new=mock_create),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        result = await provider.embed(["test"])

    assert mock_create.call_count == 2
    assert result[0] == [0.3] * 1536


async def test_retry_succeeds_after_connection_error() -> None:
    provider = _make_provider(max_retries=3)
    good_response = _make_embed_response([[0.4] * 1536])
    mock_create = AsyncMock(side_effect=[_make_connection_error(), good_response])

    with (
        patch.object(provider._client.embeddings, "create", new=mock_create),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        result = await provider.embed(["test"])

    assert mock_create.call_count == 2
    assert result[0] == [0.4] * 1536


async def test_retry_respects_retry_after_header() -> None:
    provider = _make_provider(max_retries=2)
    good_response = _make_embed_response([[0.1] * 1536])
    mock_create = AsyncMock(
        side_effect=[_make_rate_limit_error(retry_after="7"), good_response]
    )
    sleep_mock = AsyncMock()

    with (
        patch.object(provider._client.embeddings, "create", new=mock_create),
        patch("asyncio.sleep", new=sleep_mock),
    ):
        await provider.embed(["test"])

    assert any(abs(call.args[0] - 7.0) < 0.5 for call in sleep_mock.call_args_list)


# ---------------------------------------------------------------------------
# Retry exhaustion
# ---------------------------------------------------------------------------


async def test_retry_exhaustion_raises_after_max_retries() -> None:
    max_retries = 3
    provider = _make_provider(max_retries=max_retries)
    mock_create = AsyncMock(side_effect=_make_rate_limit_error())

    with (
        patch.object(provider._client.embeddings, "create", new=mock_create),
        patch("asyncio.sleep", new=AsyncMock()),
        pytest.raises(RateLimitError),
    ):
        await provider.embed(["test"])

    assert mock_create.call_count == max_retries


# ---------------------------------------------------------------------------
# Defensive truncation
# ---------------------------------------------------------------------------


async def test_truncation_long_input(caplog) -> None:
    provider = _make_provider()
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    long_text = " ".join(["word"] * 9000)
    assert len(enc.encode(long_text)) > 8000

    truncated_response = _make_embed_response([[0.1] * 1536])
    mock_create = AsyncMock(return_value=truncated_response)

    with (
        patch.object(provider._client.embeddings, "create", new=mock_create),
        caplog.at_level(logging.WARNING, logger="app.providers.openai_embeddings"),
    ):
        await provider.embed([long_text])

    assert any("truncated" in record.message.lower() for record in caplog.records)

    sent_input = mock_create.call_args.kwargs["input"]
    assert len(enc.encode(sent_input[0])) <= 8000


async def test_no_truncation_for_short_input() -> None:
    provider = _make_provider()
    short_text = "short text"
    mock_create = AsyncMock(return_value=_make_embed_response([[0.1] * 1536]))

    with patch.object(provider._client.embeddings, "create", new=mock_create):
        await provider.embed([short_text])

    sent_input = mock_create.call_args.kwargs["input"]
    assert sent_input[0] == short_text


# ---------------------------------------------------------------------------
# Ordering assertion
# ---------------------------------------------------------------------------


async def test_ordering_assertion_raises_on_shuffled_response() -> None:
    provider = _make_provider()
    shuffled_response = _make_embed_response([[0.1] * 1536, [0.2] * 1536], shuffle=True)
    mock_create = AsyncMock(return_value=shuffled_response)

    with (
        patch.object(provider._client.embeddings, "create", new=mock_create),
        pytest.raises(AssertionError, match="Unexpected response ordering"),
    ):
        await provider.embed(["a", "b"])
