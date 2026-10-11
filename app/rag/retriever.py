"""Local vector retrieval for RentOut policy chunks."""

# Keep annotations future-compatible.
from __future__ import annotations

# asyncio.to_thread is used for blocking JSON file reads.
import asyncio

# json parses the local vector store file.
import json

# math provides square root for cosine similarity norms.
import math

# Any is used for flexible filter values.
from typing import Any

# Settings provide vector store path and default top_k.
from app.core.config import get_settings

# embed_query turns the user's question into a vector.
from app.rag.embeddings import embed_query

# RetrievedChunk is the structured result returned to the API layer.
from app.rag.schemas import RetrievedChunk


async def retrieve_context(
    # Natural-language question from the user.
    question: str,
    # Optional metadata filters such as department or audience.
    filters: dict[str, Any] | None = None,
    # Optional per-request result count override.
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """Return the most relevant chunks for a user question."""

    # Read runtime settings.
    settings = get_settings()

    # Retrieval cannot work until ingestion has created the vector store.
    if not settings.vector_store_path.exists():
        raise FileNotFoundError("Vector store not found. Run POST /ingest or scripts/ingest_docs.py first.")

    # Read JSON in a worker thread so the async API event loop stays responsive.
    store = await asyncio.to_thread(_read_store)

    # Embed the user question with the same model used during ingestion.
    query_embedding = await embed_query(question)

    # Use request-provided top_k when present, otherwise use the default setting.
    limit = top_k or settings.top_k

    # Collect chunks after filtering and scoring.
    scored: list[RetrievedChunk] = []

    # Iterate over every stored chunk in the local JSON vector store.
    for item in store["chunks"]:
        # Skip chunks that do not match requested metadata filters.
        if not _metadata_matches(item["metadata"], filters):
            continue

        # Compare user query vector with this chunk vector.
        score = cosine_similarity(query_embedding, item["embedding"])

        # Convert raw JSON dictionary into a typed backend model.
        scored.append(
            RetrievedChunk(
                # Copy chunk id from storage.
                chunk_id=item["chunk_id"],
                # Copy chunk text for prompt context.
                text=item["text"],
                # Copy title from metadata.
                document_title=item["metadata"]["title"],
                # Use inferred section or fallback.
                section=item["metadata"].get("section", "General"),
                # Copy document type.
                document_type=item["metadata"]["document_type"],
                # Copy owning department.
                department=item["metadata"]["department"],
                # Copy intended audience.
                audience=item["metadata"]["audience"],
                # Copy document version.
                version=item["metadata"]["version"],
                # Copy source file path.
                source_path=item["metadata"]["source_path"],
                # Attach computed similarity score.
                score=score,
            )
        )

    # Sort best matches first.
    scored.sort(key=lambda chunk: chunk.score, reverse=True)

    # Return only top_k chunks to control prompt size and latency.
    return scored[:limit]


# Cosine similarity measures how close two vectors point in embedding space.
def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Measure vector similarity; higher means more semantically related."""

    # Dot product captures directional alignment.
    dot = sum(a * b for a, b in zip(left, right))

    # Norm is the length of the left vector.
    left_norm = math.sqrt(sum(a * a for a in left))

    # Norm is the length of the right vector.
    right_norm = math.sqrt(sum(b * b for b in right))

    # If either vector is empty/zero, similarity is undefined; return 0 safely.
    if left_norm == 0 or right_norm == 0:
        return 0.0

    # Normalize dot product by vector lengths.
    return dot / (left_norm * right_norm)


# Private helper to load the vector store JSON file.
def _read_store() -> dict[str, Any]:
    """Load the local JSON vector store from disk."""

    # Read settings so this helper uses the configured vector store path.
    settings = get_settings()

    # Read text as UTF-8 and parse JSON into a dictionary.
    return json.loads(settings.vector_store_path.read_text(encoding="utf-8"))


# Private helper to apply optional metadata filters.
def _metadata_matches(metadata: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    """Return True when a chunk satisfies all requested metadata filters."""

    # No filters means every chunk is eligible.
    if not filters:
        return True

    # Check every requested filter key/value pair.
    for key, expected in filters.items():
        # Read the actual metadata value for this key.
        actual = metadata.get(key)

        # If expected is a list, allow any value in the list.
        if isinstance(expected, list):
            # Reject the chunk when its actual value is not in the allowed list.
            if actual not in expected:
                return False

        # If expected is a scalar, require exact equality.
        elif actual != expected:
            return False

    # If every filter passed, the chunk matches.
    return True