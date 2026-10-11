"""Text chunking utilities for the RentOut policy corpus."""

# Keep annotations future-compatible.
from __future__ import annotations

# dataclass creates a small typed container for chunk data.
from dataclasses import dataclass


# frozen=True makes chunks immutable after creation, which prevents accidental edits.
@dataclass(frozen=True)
class TextChunk:
    """One retrievable unit stored in the local vector store."""

    # Stable id used in storage and debugging.
    chunk_id: str

    # Text that will be embedded and later used as LLM context.
    text: str

    # Metadata copied from the source document plus inferred section.
    metadata: dict[str, str]


# This function converts one full document into multiple retrievable chunks.
def semantic_chunk_text(
    # Full source document text extracted from DOCX.
    text: str,
    # Document metadata, such as title, department, audience, and version.
    metadata: dict[str, str],
    # Approximate maximum characters allowed per chunk.
    chunk_size: int,
    # Number of trailing characters repeated into the next chunk.
    chunk_overlap: int,
) -> list[TextChunk]:
    """Split a document into paragraph-aware retrieval chunks."""

    # Split on newlines, trim whitespace, and drop blank paragraphs.
    paragraphs = [para.strip() for para in text.split("\n") if para.strip()]

    # Store all finished chunks here.
    chunks: list[TextChunk] = []

    # Store paragraph strings for the chunk currently being built.
    current: list[str] = []

    # Track approximate current chunk length without repeatedly joining strings.
    current_len = 0

    # Process each paragraph in document order.
    for paragraph in paragraphs:
        # Measure this paragraph so we know whether it fits in the current chunk.
        para_len = len(paragraph)

        # If current already has text and this paragraph would exceed chunk_size,
        # finish the current chunk before starting the next one.
        if current and current_len + para_len + 1 > chunk_size:
            # Join paragraphs into final chunk text.
            chunk_text = "\n".join(current)

            # Create and store a TextChunk object.
            chunks.append(
                TextChunk(
                    # Chunk id is deterministic: document id plus chunk number.
                    chunk_id=f"{metadata['document_id']}:c{len(chunks) + 1}",
                    # Store the chunk text.
                    text=chunk_text,
                    # Copy metadata and add an inferred section label.
                    metadata={**metadata, "section": _infer_section(chunk_text)},
                )
            )

            # Capture trailing text so the next chunk keeps boundary context.
            overlap_text = chunk_text[-chunk_overlap:] if chunk_overlap > 0 else ""

            # Start the new chunk with overlap plus the paragraph that did not fit.
            current = [overlap_text, paragraph] if overlap_text else [paragraph]

            # Recalculate current length after resetting the chunk.
            current_len = sum(len(item) for item in current)
        else:
            # Paragraph fits, so append it to the current chunk.
            current.append(paragraph)

            # Add paragraph length plus one approximate newline separator.
            current_len += para_len + 1

    # After the loop, flush any remaining text into a final chunk.
    if current:
        # Join final paragraphs into text.
        chunk_text = "\n".join(current)

        # Store the final TextChunk.
        chunks.append(
            TextChunk(
                # Use next chunk number for the id.
                chunk_id=f"{metadata['document_id']}:c{len(chunks) + 1}",
                # Store final chunk text.
                text=chunk_text,
                # Copy metadata and infer section.
                metadata={**metadata, "section": _infer_section(chunk_text)},
            )
        )

    # Return every chunk for embedding/storage.
    return chunks


# Helper is private because only this module needs section inference.
def _infer_section(text: str) -> str:
    """Use the first short heading-like line as a lightweight section label."""

    # Take the first line from the chunk.
    first_line = text.splitlines()[0].strip()

    # Treat short non-sentence first lines as headings.
    if len(first_line) < 80 and not first_line.endswith("."):
        return first_line

    # Fall back when the first line looks like body text.
    return "General"