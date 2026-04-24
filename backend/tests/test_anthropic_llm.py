"""Tests for AnthropicLLMProvider. All network I/O is mocked."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from anthropic import APIConnectionError, RateLimitError

from app.providers.anthropic_llm import AnthropicLLMProvider
from app.providers.llm import ChatMessage, GenerationResult, get_llm_provider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(max_retries: int = 5) -> AnthropicLLMProvider:
    return AnthropicLLMProvider(
        api_key="test-key",
        default_model="claude-haiku-4-5",
        strong_model="claude-sonnet-4-5",
        max_retries=max_retries,
    )


def _make_message_response(text: str = "Hello!") -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage = MagicMock(input_tokens=10, output_tokens=5)
    resp.model = "claude-haiku-4-5"
    resp.stop_reason = "end_turn"
    return resp


def _make_rate_limit_error(retry_after: str | None = None) -> RateLimitError:
    headers = {"retry-after": retry_after} if retry_after else {}
    response = httpx.Response(
        429,
        headers=headers,
        request=httpx.Request("POST", "https://api.anthropic.com"),
    )
    return RateLimitError("Rate limit", response=response, body=None)


def _make_connection_error() -> APIConnectionError:
    return APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))


# ---------------------------------------------------------------------------
# Settings validation
# ---------------------------------------------------------------------------


def test_settings_validation_raises_when_anthropic_key_missing() -> None:
    from pydantic import ValidationError
    from app.config import Settings

    with patch.dict(os.environ, {}, clear=False) as env:
        env.pop("ANTHROPIC_API_KEY", None)
        with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
            Settings(LLM_PROVIDER="anthropic", _env_file=None)


def test_settings_validation_passes_with_key() -> None:
    from app.config import Settings

    s = Settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="sk-ant-test")
    assert s.LLM_PROVIDER == "anthropic"


def test_factory_returns_anthropic_provider() -> None:
    from app.config import Settings

    s = Settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="sk-ant-test")
    provider = get_llm_provider(s)
    assert isinstance(provider, AnthropicLLMProvider)


# ---------------------------------------------------------------------------
# identifier / model_for_tier
# ---------------------------------------------------------------------------


def test_identifier_format() -> None:
    provider = _make_provider()
    assert provider.identifier == "anthropic:claude-haiku-4-5:v1"


def test_model_for_tier_default() -> None:
    provider = _make_provider()
    assert provider.model_for_tier("default") is None


def test_model_for_tier_strong() -> None:
    provider = _make_provider()
    assert provider.model_for_tier("strong") == "claude-sonnet-4-5"


# ---------------------------------------------------------------------------
# generate() happy path
# ---------------------------------------------------------------------------


async def test_generate_happy_path() -> None:
    provider = _make_provider()
    mock_create = AsyncMock(return_value=_make_message_response("Test answer"))

    with patch.object(provider._client.messages, "create", new=mock_create):
        result = await provider.generate(
            messages=[ChatMessage(role="user", content="hello")],
            system_prompt="You are helpful.",
        )

    assert isinstance(result, GenerationResult)
    assert result.text == "Test answer"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.stop_reason == "end_turn"


async def test_generate_passes_system_as_top_level() -> None:
    provider = _make_provider()
    mock_create = AsyncMock(return_value=_make_message_response())

    with patch.object(provider._client.messages, "create", new=mock_create):
        await provider.generate(
            messages=[ChatMessage(role="user", content="hi")],
            system_prompt="Be concise.",
        )

    kwargs = mock_create.call_args.kwargs
    assert kwargs["system"] == "Be concise."
    assert all(m["role"] != "system" for m in kwargs["messages"])


async def test_generate_filters_system_role_messages() -> None:
    provider = _make_provider()
    mock_create = AsyncMock(return_value=_make_message_response())

    with patch.object(provider._client.messages, "create", new=mock_create):
        await provider.generate(
            messages=[
                ChatMessage(role="system", content="ignored"),
                ChatMessage(role="user", content="hello"),
            ],
            system_prompt="system prompt",
        )

    sent = mock_create.call_args.kwargs["messages"]
    assert len(sent) == 1
    assert sent[0]["role"] == "user"


# ---------------------------------------------------------------------------
# stream() happy path
# ---------------------------------------------------------------------------


async def test_stream_yields_tokens() -> None:
    provider = _make_provider()

    final_msg = MagicMock()
    final_msg.usage = MagicMock(input_tokens=8, output_tokens=3)

    async def fake_text_stream():
        for token in ["Hello", " ", "world"]:
            yield token

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_ctx)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_stream_ctx.text_stream = fake_text_stream()
    mock_stream_ctx.get_final_message = AsyncMock(return_value=final_msg)

    with patch.object(provider._client.messages, "stream", return_value=mock_stream_ctx):
        tokens = []
        async for token in provider.stream(
            messages=[ChatMessage(role="user", content="hi")],
            system_prompt="Be helpful.",
        ):
            tokens.append(token)

    assert tokens == ["Hello", " ", "world"]


# ---------------------------------------------------------------------------
# Retry: generate()
# ---------------------------------------------------------------------------


async def test_generate_retries_after_429() -> None:
    provider = _make_provider(max_retries=3)
    good = _make_message_response("ok")
    mock_create = AsyncMock(side_effect=[_make_rate_limit_error(), good])

    with (
        patch.object(provider._client.messages, "create", new=mock_create),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        result = await provider.generate(
            messages=[ChatMessage(role="user", content="hi")],
            system_prompt="s",
        )

    assert mock_create.call_count == 2
    assert result.text == "ok"


async def test_generate_retries_after_connection_error() -> None:
    provider = _make_provider(max_retries=3)
    good = _make_message_response("recovered")
    mock_create = AsyncMock(side_effect=[_make_connection_error(), good])

    with (
        patch.object(provider._client.messages, "create", new=mock_create),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        result = await provider.generate(
            messages=[ChatMessage(role="user", content="hi")],
            system_prompt="s",
        )

    assert mock_create.call_count == 2
    assert result.text == "recovered"


async def test_generate_exhaustion_raises() -> None:
    max_retries = 3
    provider = _make_provider(max_retries=max_retries)
    mock_create = AsyncMock(side_effect=_make_rate_limit_error())

    with (
        patch.object(provider._client.messages, "create", new=mock_create),
        patch("asyncio.sleep", new=AsyncMock()),
        pytest.raises(RateLimitError),
    ):
        await provider.generate(
            messages=[ChatMessage(role="user", content="hi")],
            system_prompt="s",
        )

    assert mock_create.call_count == max_retries
