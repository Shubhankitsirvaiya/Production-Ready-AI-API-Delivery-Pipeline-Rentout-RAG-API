"""Async OpenAI embedding helpers.

Embeddings convert text into vectors. The retriever compares the user's question
vector against stored document chunk vectors to find semantically similar policy
content.
"""

from __future__ import annotations

from openai import AsyncOpenAI

from app.core.config import get_settings


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Create embeddings for many strings in one API call.

    Arguments:
    - texts: The chunk texts to embed. Batching them into one request is faster
      and cheaper operationally than calling the API once per chunk.

    Returns:
    - A list of float vectors in the same order as the input texts.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for embedding generation.")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


async def embed_query(text: str) -> list[float]:
    """Embed one user question using the same model as document chunks."""
    return (await embed_texts([text]))[0]