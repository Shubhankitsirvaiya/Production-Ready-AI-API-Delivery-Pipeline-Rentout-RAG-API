"""Document ingestion pipeline shared by the API and CLI script."""

# Keep annotations future-compatible.
from __future__ import annotations

# asyncio.to_thread lets blocking DOCX/file operations coexist with async code.
import asyncio

# json writes the local vector store in an inspectable format.
import json

# Path gives typed filesystem paths.
from pathlib import Path

# python-docx reads Word documents.
from docx import Document

# Settings provide source folders, chunking params, and vector store path.
from app.core.config import get_settings

# semantic_chunk_text splits full documents into retrievable chunks.
from app.rag.chunking import semantic_chunk_text

# embed_texts creates OpenAI embeddings for each chunk.
from app.rag.embeddings import embed_texts

# IngestResponse is returned by API and CLI ingestion.
from app.rag.schemas import IngestResponse


async def ingest_documents() -> IngestResponse:
    """Build or rebuild the RentOut vector store from source DOCX files."""

    # Read runtime configuration.
    settings = get_settings()

    # Source documents live under app/data/source_docs.
    source_dir = settings.data_dir / "source_docs"

    # Find all Word documents in stable sorted order.
    docx_paths = sorted(source_dir.glob("*.docx"))

    # Fail clearly if the corpus has not been created or copied.
    if not docx_paths:
        raise FileNotFoundError(f"No DOCX files found in {source_dir}")

    # Collect chunks from every document before embedding.
    all_chunks = []

    # Process one DOCX file at a time.
    for path in docx_paths:
        # Read DOCX text and metadata in a thread because python-docx is blocking.
        text, metadata = await asyncio.to_thread(_read_docx, path)

        # Split the document into chunk objects using configured sizes.
        chunks = semantic_chunk_text(text, metadata, settings.chunk_size, settings.chunk_overlap)

        # Add this document's chunks to the global list.
        all_chunks.extend(chunks)

    # Create embeddings for every chunk text in one batched OpenAI call.
    embeddings = await embed_texts([chunk.text for chunk in all_chunks])

    # Build the JSON payload that becomes the local vector store.
    payload = {
        # Record model name so readers know which embedding model created vectors.
        "embedding_model": settings.openai_embedding_model,
        # Store chunk text, metadata, and vector side by side.
        "chunks": [
            {
                # Stable chunk id.
                "chunk_id": chunk.chunk_id,
                # Original chunk text.
                "text": chunk.text,
                # Metadata used for filters and citations.
                "metadata": chunk.metadata,
                # Numeric vector returned by OpenAI.
                "embedding": embedding,
            }
            # Pair each chunk with the embedding at the same position.
            for chunk, embedding in zip(all_chunks, embeddings)
        ],
    }

    # Ensure the vector store folder exists before writing the JSON file.
    settings.vector_store_path.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON in a thread because file writes are blocking.
    await asyncio.to_thread(
        # Function to call in the worker thread.
        settings.vector_store_path.write_text,
        # JSON string with readable indentation.
        json.dumps(payload, ensure_ascii=False, indent=2),
        # File encoding.
        "utf-8",
    )

    # Return a summary for API users and CLI output.
    return IngestResponse(
        # Number of documents processed.
        documents=len(docx_paths),
        # Number of chunks stored.
        chunks=len(all_chunks),
        # Location of generated vector store.
        vector_store_path=str(settings.vector_store_path),
    )


# Private helper that reads one Word document.
def _read_docx(path: Path) -> tuple[str, dict[str, str]]:
    """Extract paragraph text and metadata from one Word document."""

    # Open the DOCX file with python-docx.
    document = Document(path)

    # Extract non-empty paragraphs and strip extra whitespace.
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]

    # Join paragraphs into one newline-separated text block.
    text = "\n".join(paragraphs)

    # Extract metadata from the first few header-style paragraphs.
    metadata = _extract_metadata(paragraphs, path)

    # Return both full text and metadata.
    return text, metadata


# Private helper that reads metadata from predictable header lines.
def _extract_metadata(paragraphs: list[str], path: Path) -> dict[str, str]:
    """Read standard metadata fields from the top of a policy document."""

    # Start with safe defaults in case a document is missing header fields.
    metadata = {
        # Use filename stem as fallback document id.
        "document_id": path.stem.lower().replace(" ", "-"),
        # Use filename stem as fallback title.
        "title": path.stem.replace("_", " "),
        # Default type.
        "document_type": "policy",
        # Default department.
        "department": "support",
        # Default audience.
        "audience": "customer",
        # Default version.
        "version": "v1.0",
        # Always store source path.
        "source_path": str(path),
    }

    # Only inspect the first few paragraphs because metadata lives at the top.
    for paragraph in paragraphs[:12]:
        # Skip lines that are not in Key: Value format.
        if ":" not in paragraph:
            continue

        # Split into key and value only at the first colon.
        key, value = paragraph.split(":", 1)

        # Normalize keys into snake_case.
        normalized = key.strip().lower().replace(" ", "_")

        # Only accept fields we intentionally support.
        if normalized in {"title", "document_type", "department", "audience", "version", "effective_date"}:
            # Store the cleaned value in metadata.
            metadata[normalized] = value.strip()

    # Return metadata for chunking, filtering, and citations.
    return metadata