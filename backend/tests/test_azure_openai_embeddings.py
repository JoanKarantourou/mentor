"""Tests for AzureOpenAIEmbeddingProvider and related admin endpoints.

No real Azure API calls are made here. All network I/O is mocked at the
AsyncAzureOpenAI client layer.
"""

import logging
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import APIConnectionError, RateLimitError
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.chunk import Chunk
from app.models.document import Document
from app.providers.azure_openai_embeddings import AzureOpenAIEmbeddingProvider
from app.providers.embeddings import get_embedding_provider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(max_retries: int = 5) -> AzureOpenAIEmbeddingProvider:
    return AzureOpenAIEmbeddingProvider(
        endpoint="https://test.openai.azure.com",
        api_key="test-key",
        deployment="text-embedding-3-small",
        api_version="2024-02-01",
        max_retries=max_retries,
    )


def _make_embed_response(vectors: list[list[float]], shuffle: bool = False) -> MagicMock:
    """Build a mock response matching openai EmbeddingCreateResponse structure."""
    response = MagicMock()
    items = []
    indices = list(range(len(vectors)))
    if shuffle and len(indices) > 1:
        # Swap first two entries so index order is wrong.
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
        request=httpx.Request("POST", "https://test.openai.azure.com"),
    )
    return RateLimitError("Rate limit exceeded", response=response, body=None)


def _make_connection_error() -> APIConnectionError:
    return APIConnectionError(request=httpx.Request("POST", "https://test.openai.azure.com"))


# ---------------------------------------------------------------------------
# Settings validation
# ---------------------------------------------------------------------------


def test_settings_validation_raises_when_azure_fields_missing() -> None:
    """Settings must reject azure_openai provider without credentials."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="AZURE_OPENAI_ENDPOINT"):
        from app.config import Settings

        Settings(EMBEDDING_PROVIDER="azure_openai")


def test_settings_validation_passes_with_all_azure_fields() -> None:
    from app.config import Settings

    s = Settings(
        EMBEDDING_PROVIDER="azure_openai",
        AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com",
        AZURE_OPENAI_API_KEY="key",
        AZURE_OPENAI_EMBEDDING_DEPLOYMENT="my-deployment",
    )
    assert s.EMBEDDING_PROVIDER == "azure_openai"


def test_factory_returns_azure_provider() -> None:
    from app.config import Settings

    s = Settings(
        EMBEDDING_PROVIDER="azure_openai",
        AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com",
        AZURE_OPENAI_API_KEY="key",
        AZURE_OPENAI_EMBEDDING_DEPLOYMENT="my-deployment",
    )
    provider = get_embedding_provider(s)
    assert isinstance(provider, AzureOpenAIEmbeddingProvider)


# ---------------------------------------------------------------------------
# identifier
# ---------------------------------------------------------------------------


def test_identifier_includes_deployment_name() -> None:
    provider = _make_provider()
    assert provider.identifier == "azure-openai:text-embedding-3-small:v1"


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


async def test_embed_passes_deployment_as_model() -> None:
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
    mock_create = AsyncMock(
        side_effect=[_make_rate_limit_error(), good_response]
    )

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
    mock_create = AsyncMock(
        side_effect=[_make_connection_error(), good_response]
    )

    with (
        patch.object(provider._client.embeddings, "create", new=mock_create),
        patch("asyncio.sleep", new=AsyncMock()),
    ):
        result = await provider.embed(["test"])

    assert mock_create.call_count == 2
    assert result[0] == [0.4] * 1536


async def test_retry_respects_retry_after_header() -> None:
    """When Retry-After header is present, wait uses that value."""
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

    # tenacity calls asyncio.sleep with the wait duration
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
    # Build a text that is definitely over 8000 tokens.
    long_text = " ".join(["word"] * 9000)
    assert len(enc.encode(long_text)) > 8000

    truncated_response = _make_embed_response([[0.1] * 1536])
    mock_create = AsyncMock(return_value=truncated_response)

    with (
        patch.object(provider._client.embeddings, "create", new=mock_create),
        caplog.at_level(logging.WARNING, logger="app.providers.azure_openai_embeddings"),
    ):
        await provider.embed([long_text])

    # Warning should have been logged about truncation.
    assert any("truncated" in record.message.lower() for record in caplog.records)

    # The actual text sent to the API must be ≤ 8000 tokens.
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
    # Two vectors so there is something to shuffle.
    shuffled_response = _make_embed_response([[0.1] * 1536, [0.2] * 1536], shuffle=True)
    mock_create = AsyncMock(return_value=shuffled_response)

    with (
        patch.object(provider._client.embeddings, "create", new=mock_create),
        pytest.raises(AssertionError, match="Unexpected response ordering"),
    ):
        await provider.embed(["a", "b"])


# ---------------------------------------------------------------------------
# /admin/embeddings/status integration
# ---------------------------------------------------------------------------


async def test_embeddings_status_endpoint(
    async_client,
    test_engine: AsyncEngine,
) -> None:
    """Seed chunks with two distinct embedding_model values and verify status counts."""
    current_model = "stub-v1"  # matches StubEmbeddingProvider used in async_client fixture
    old_model = "old-provider:v0"

    # Create a document to attach chunks to.
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        filename="test.md",
        content_type="text/markdown",
        size_bytes=10,
        blob_path=f"documents/{doc_id}/test.md",
        status="indexed",
        file_category="document",
        normalized_content="test",
    )
    async with AsyncSession(test_engine) as session:
        session.add(doc)
        await session.commit()

    # Insert 3 current-model chunks and 2 stale chunks.
    async with AsyncSession(test_engine) as session:
        for i in range(3):
            session.add(
                Chunk(
                    document_id=doc_id,
                    chunk_index=i,
                    text=f"chunk {i}",
                    token_count=5,
                    embedding=[0.1] * 1536,
                    embedding_model=current_model,
                    meta={},
                )
            )
        for i in range(2):
            session.add(
                Chunk(
                    document_id=doc_id,
                    chunk_index=10 + i,
                    text=f"old chunk {i}",
                    token_count=5,
                    embedding=[0.2] * 1536,
                    embedding_model=old_model,
                    meta={},
                )
            )
        await session.commit()

    response = await async_client.get("/admin/embeddings/status")
    assert response.status_code == 200
    data = response.json()

    assert data["current_provider_identifier"] == current_model
    assert data["chunks_by_model"][current_model] == 3
    assert data["chunks_by_model"][old_model] == 2
    assert data["stale_chunks"] == 2
    assert data["stale_documents"] == 1


async def test_embeddings_status_no_stale(async_client, test_engine: AsyncEngine) -> None:
    """When all chunks match the current model, stale counts are zero."""
    current_model = "stub-v1"
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        filename="fresh.md",
        content_type="text/markdown",
        size_bytes=10,
        blob_path=f"documents/{doc_id}/fresh.md",
        status="indexed",
        file_category="document",
        normalized_content="fresh",
    )
    async with AsyncSession(test_engine) as session:
        session.add(doc)
        await session.commit()

    async with AsyncSession(test_engine) as session:
        for i in range(2):
            session.add(
                Chunk(
                    document_id=doc_id,
                    chunk_index=i,
                    text=f"chunk {i}",
                    token_count=5,
                    embedding=[0.1] * 1536,
                    embedding_model=current_model,
                    meta={},
                )
            )
        await session.commit()

    response = await async_client.get("/admin/embeddings/status")
    assert response.status_code == 200
    data = response.json()
    assert data["stale_chunks"] == 0
    assert data["stale_documents"] == 0


# ---------------------------------------------------------------------------
# /admin/reindex with only_stale
# ---------------------------------------------------------------------------


async def test_reindex_only_stale_skips_current_chunks(
    async_client,
    test_engine: AsyncEngine,
) -> None:
    """only_stale=true should not reindex documents whose chunks are all current."""
    current_model = "stub-v1"
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        filename="current.md",
        content_type="text/markdown",
        size_bytes=10,
        blob_path=f"documents/{doc_id}/current.md",
        status="indexed",
        file_category="document",
        normalized_content="content that is already current",
    )
    async with AsyncSession(test_engine) as session:
        session.add(doc)
        await session.commit()

    async with AsyncSession(test_engine) as session:
        session.add(
            Chunk(
                document_id=doc_id,
                chunk_index=0,
                text="already current",
                token_count=3,
                embedding=[0.1] * 1536,
                embedding_model=current_model,
                meta={},
            )
        )
        await session.commit()

    response = await async_client.post("/admin/reindex", json={"only_stale": True})
    assert response.status_code == 202
    assert response.json()["reindexed"] == 0
