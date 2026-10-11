"""Text chunking utilities for the RentOut policy corpus.

The goal is not to split text randomly. Good RAG chunks should preserve enough
context for the LLM to answer correctly while staying small enough for efficient
embedding and retrieval. This file uses paragraph-aware chunking with overlap so
neighboring chunks share a little context.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    """One retrievable unit stored in the local vector store.

    chunk_id: Stable id built from the source document id and chunk number.
    text: The actual policy text that will be embedded and later shown to GPT.
    metadata: Search/filter fields such as title, department, audience, version.
    """

    chunk_id: str
    text: str
    metadata: dict[str, str]


def semantic_chunk_text(
    text: str,
    metadata: dict[str, str],
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    """Split a document into retrieval chunks.

    Arguments:
    - text: Full document text extracted from a DOCX file.
    - metadata: Document-level fields copied onto every chunk for citation and
      filtering.
    - chunk_size: Approximate maximum number of characters per chunk. Smaller
      chunks retrieve precisely; larger chunks preserve more context.
    - chunk_overlap: Number of trailing characters copied into the next chunk so
      answers do not lose context at chunk boundaries.
    """
    paragraphs = [para.strip() for para in text.split("\n") if para.strip()]
    chunks: list[TextChunk] = []
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        para_len = len(paragraph)

        # If adding this paragraph would exceed the configured chunk budget, we
        # close the current chunk before starting the next one.
        if current and current_len + para_len + 1 > chunk_size:
            chunk_text = "\n".join(current)
            chunks.append(
                TextChunk(
                    chunk_id=f"{metadata['document_id']}:c{len(chunks) + 1}",
                    text=chunk_text,
                    metadata={**metadata, "section": _infer_section(chunk_text)},
                )
            )

            # Overlap is a simple way to protect context that sits at the edge of
            # two chunks. For example, a policy heading at the end of one chunk
            # can still influence retrieval for the next chunk.
            overlap_text = chunk_text[-chunk_overlap:] if chunk_overlap > 0 else ""
            current = [overlap_text, paragraph] if overlap_text else [paragraph]
            current_len = sum(len(item) for item in current)
        else:
            current.append(paragraph)
            current_len += para_len + 1

    # Flush the final partial chunk after the loop.
    if current:
        chunk_text = "\n".join(current)
        chunks.append(
            TextChunk(
                chunk_id=f"{metadata['document_id']}:c{len(chunks) + 1}",
                text=chunk_text,
                metadata={**metadata, "section": _infer_section(chunk_text)},
            )
        )
    return chunks


def _infer_section(text: str) -> str:
    """Use the first short non-sentence line as a lightweight section label."""
    first_line = text.splitlines()[0].strip()
    if len(first_line) < 80 and not first_line.endswith("."):
        return first_line
    return "General"