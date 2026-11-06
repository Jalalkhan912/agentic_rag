import asyncio
import logging

from openai import AsyncOpenAI, RateLimitError
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,  # None → api.openai.com
        )
    return _client


async def _embed_batch(client: AsyncOpenAI, batch: list[str]) -> list[list[float]]:
    """Embed one batch, waiting and retrying when the API rate-limits us.

    Free tiers (e.g. Gemini) have per-minute quotas, so a large document can
    exceed them; the SDK's built-in retries back off for only a second or two.
    """
    for attempt in range(settings.embedding_max_retries + 1):
        try:
            response = await client.embeddings.create(
                model=settings.openai_embedding_model,
                input=batch,
                dimensions=settings.openai_embedding_dimensions,
            )
            # Results carry their input index; sort to be safe
            return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
        except RateLimitError:
            if attempt == settings.embedding_max_retries:
                raise
            delay = min(5 * 2 ** attempt, 60)
            logger.warning("Embedding rate-limited; retrying in %ss", delay)
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts, in batches of settings.embedding_batch_size.
    Returns a list of embedding vectors in the same order as the input.
    """
    client = get_openai_client()
    size = settings.embedding_batch_size
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), size):
        all_embeddings.extend(await _embed_batch(client, texts[i: i + size]))

    return all_embeddings


async def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    results = await embed_texts([text])
    return results[0]
