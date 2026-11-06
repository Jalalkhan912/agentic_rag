"""Tests for batching and rate-limit retries in the embeddings service."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import RateLimitError

from app.services import embeddings


def _response(n):
    return SimpleNamespace(data=[SimpleNamespace(index=i, embedding=[float(i)]) for i in range(n)])


def _rate_limit_error():
    req = httpx.Request("POST", "https://example.test/embeddings")
    return RateLimitError("quota", response=httpx.Response(429, request=req), body=None)


def _client(create):
    return SimpleNamespace(embeddings=SimpleNamespace(create=create))


@pytest.mark.asyncio
async def test_texts_are_split_into_batches_of_configured_size():
    create = AsyncMock(side_effect=lambda **kw: _response(len(kw["input"])))
    with patch.object(embeddings, "get_openai_client", return_value=_client(create)), \
         patch.object(embeddings.settings, "embedding_batch_size", 100):
        result = await embeddings.embed_texts([f"t{i}" for i in range(250)])

    assert len(result) == 250
    assert [len(c.kwargs["input"]) for c in create.await_args_list] == [100, 100, 50]


@pytest.mark.asyncio
async def test_rate_limit_is_retried_then_succeeds():
    create = AsyncMock(side_effect=[_rate_limit_error(), _response(2)])
    sleep = AsyncMock()
    with patch.object(embeddings, "get_openai_client", return_value=_client(create)), \
         patch.object(embeddings.asyncio, "sleep", sleep):
        result = await embeddings.embed_texts(["a", "b"])

    assert len(result) == 2
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_rate_limit_gives_up_after_max_retries():
    create = AsyncMock(side_effect=_rate_limit_error())
    with patch.object(embeddings, "get_openai_client", return_value=_client(create)), \
         patch.object(embeddings.asyncio, "sleep", AsyncMock()), \
         patch.object(embeddings.settings, "embedding_max_retries", 2):
        with pytest.raises(RateLimitError):
            await embeddings.embed_texts(["a"])
    assert create.await_count == 3
