"""Local vector retrieval for RentOut policy chunks.

This project stores vectors in a JSON file to keep deployment simple. The code is
written behind a retriever function so a future version can swap the JSON store
for Chroma, Pinecone, pgvector, or another managed vector database without
changing the FastAPI route contract.
"""

from __future__ import annotations

import asyncio
import json
import math
from typing import Any

from app.core.config import get_settings
from app.rag.embeddings import embed_query
from app.rag.schemas import RetrievedChunk


async def retrieve_context(
    question: str,
    filters: dict[str, Any] | None = None,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """Return the most relevant chunks for a user question.

    Arguments:
    - question: The natural-language question from the API request.
    - filters: Optional metadata filters, such as {"department": "finance"} or
      {"audience": ["customer", "support_agent"]}. Filters narrow the search.
    - top_k: Optional per-request override for how many chunks to return. If not
      supplied, the default from `.env` is used.
    """
    settings = get_settings()
    if not settings.vector_store_path.exists():
        raise FileNotFoundError("Vector store not found. Run POST /ingest or scripts/ingest_docs.py first.")

    # Reading a JSON file is blocking I/O. asyncio.to_thread keeps the event loop
    # available for other requests while the file read happens in a worker thread.
    store = await asyncio.to_thread(_read_store)

    # The query must be embedded with the same embedding model used during
    # ingestion; otherwise cosine similarity scores are not meaningful.
    query_embedding = await embed_query(question)
    limit = top_k or settings.top_k

    scored: list[RetrievedChunk] = []
    for item in store["chunks"]:
        if not _metadata_matches(item["metadata"], filters):
            continue
        score = cosine_similarity(query_embedding, item["embedding"])
        scored.append(
            RetrievedChunk(
                chunk_id=item["chunk_id"],
                text=item["text"],
                document_title=item["metadata"]["title"],
                section=item["metadata"].get("section", "General"),
                document_type=item["metadata"]["document_type"],
                department=item["metadata"]["department"],
                audience=item["metadata"]["audience"],
                version=item["metadata"]["version"],
                source_path=item["metadata"]["source_path"],
                score=score,
            )
        )

    # Highest cosine similarity means the chunk is semantically closest to the
    # question. Only top_k chunks are sent to GPT to control cost and latency.
    scored.sort(key=lambda chunk: chunk.score, reverse=True)
    return scored[:limit]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Measure vector similarity from -1 to 1; higher is more related."""
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _read_store() -> dict[str, Any]:
    """Load the local JSON vector store from disk."""
    settings = get_settings()
    return json.loads(settings.vector_store_path.read_text(encoding="utf-8"))


def _metadata_matches(metadata: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    """Return True when a chunk satisfies all requested metadata filters."""
    if not filters:
        return True
    for key, expected in filters.items():
        actual = metadata.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True