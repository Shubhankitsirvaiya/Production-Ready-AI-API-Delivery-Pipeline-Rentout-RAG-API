"""Document ingestion pipeline shared by the API and CLI script.

This file turns RentOut DOCX policies into a local vector store:
1. Read each DOCX document.
2. Extract document metadata from the header fields.
3. Split the text into overlapping chunks.
4. Generate OpenAI embeddings for each chunk.
5. Save text, metadata, and vectors into a JSON file.

Keeping ingestion in this module lets both POST /ingest and
`scripts/ingest_docs.py` run the exact same backend logic.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from docx import Document

from app.core.config import get_settings
from app.rag.chunking import semantic_chunk_text
from app.rag.embeddings import embed_texts
from app.rag.schemas import IngestResponse


async def ingest_documents() -> IngestResponse:
    """Build or rebuild the RentOut vector store from source DOCX files."""
    settings = get_settings()
    source_dir = settings.data_dir / "source_docs"
    docx_paths = sorted(source_dir.glob("*.docx"))
    if not docx_paths:
        raise FileNotFoundError(f"No DOCX files found in {source_dir}")

    all_chunks = []
    for path in docx_paths:
        # python-docx is a synchronous library, so we run it in a thread. That
        # keeps the async API from blocking while a document is being parsed.
        text, metadata = await asyncio.to_thread(_read_docx, path)

        # chunk_size and chunk_overlap come from `.env`. Tuning these values is a
        # normal RAG iteration task: more overlap improves continuity, but it
        # increases storage and prompt size.
        chunks = semantic_chunk_text(text, metadata, settings.chunk_size, settings.chunk_overlap)
        all_chunks.extend(chunks)

    # Embeddings are generated after chunking because retrieval operates on
    # chunks, not full documents. The order of embeddings matches all_chunks.
    embeddings = await embed_texts([chunk.text for chunk in all_chunks])
    payload = {
        "embedding_model": settings.openai_embedding_model,
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "metadata": chunk.metadata,
                "embedding": embedding,
            }
            for chunk, embedding in zip(all_chunks, embeddings)
        ],
    }

    # The local vector store is just JSON for teaching. It is intentionally easy
    # to open and inspect. A production version would replace only this storage
    # boundary with a real vector database.
    settings.vector_store_path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(
        settings.vector_store_path.write_text,
        json.dumps(payload, ensure_ascii=False, indent=2),
        "utf-8",
    )
    return IngestResponse(
        documents=len(docx_paths),
        chunks=len(all_chunks),
        vector_store_path=str(settings.vector_store_path),
    )


def _read_docx(path: Path) -> tuple[str, dict[str, str]]:
    """Extract paragraph text and metadata from one Word document."""
    document = Document(path)
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    text = "\n".join(paragraphs)
    metadata = _extract_metadata(paragraphs, path)
    return text, metadata


def _extract_metadata(paragraphs: list[str], path: Path) -> dict[str, str]:
    """Read standard metadata fields from the top of a policy document.

    The generated RentOut documents start with fields like `Title:`,
    `Department:`, and `Audience:`. These values become retrieval filters and
    citation metadata.
    """
    metadata = {
        "document_id": path.stem.lower().replace(" ", "-"),
        "title": path.stem.replace("_", " "),
        "document_type": "policy",
        "department": "support",
        "audience": "customer",
        "version": "v1.0",
        "source_path": str(path),
    }
    for paragraph in paragraphs[:12]:
        if ":" not in paragraph:
            continue
        key, value = paragraph.split(":", 1)
        normalized = key.strip().lower().replace(" ", "_")
        if normalized in {"title", "document_type", "department", "audience", "version", "effective_date"}:
            metadata[normalized] = value.strip()
    return metadata