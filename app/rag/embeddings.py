"""Async OpenAI embedding helpers."""

# Keep annotations future-compatible.
from __future__ import annotations

# AsyncOpenAI lets embedding calls run without blocking the event loop.
from openai import AsyncOpenAI

# Settings provide the API key and embedding model name.
from app.core.config import get_settings


# Create embeddings for a batch of strings.
async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Create embeddings for many strings in one API call."""

    # Read runtime configuration.
    settings = get_settings()

    # Embeddings require an OpenAI key; fail clearly if it is missing.
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for embedding generation.")

    # Create an async OpenAI client using the configured key.
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Await the network call to OpenAI's embedding endpoint.
    response = await client.embeddings.create(
        # Use the configured embedding model.
        model=settings.openai_embedding_model,
        # Send all texts as one batch request.
        input=texts,
    )

    # Return only the raw vectors, preserving the same order as input texts.
    return [item.embedding for item in response.data]


# Create one embedding for a user query.
async def embed_query(text: str) -> list[float]:
    """Embed one user question using the same function as document chunks."""

    # Reuse embed_texts for consistency, then take the first and only vector.
    return (await embed_texts([text]))[0]