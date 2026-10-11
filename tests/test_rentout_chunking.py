# Import the chunking function we want to verify.
from app.rag.chunking import semantic_chunk_text


# Verify chunking creates multiple chunks and keeps metadata attached.
def test_semantic_chunking_preserves_metadata() -> None:
    # Build a repeated sample document large enough to require multiple chunks.
    text = "\n".join(
        [
            # Heading-like first line should become section metadata.
            "Cancellation Rules",
            # Body paragraph one.
            "Customers may cancel before delivery when the route has not been dispatched.",
            # Body paragraph two.
            "Active rental returns may require pickup and inspection before refund decisions.",
        ]
        # Repeat the sample paragraphs to exceed the chunk_size used below.
        * 10
    )

    # Metadata imitates what ingestion extracts from a DOCX document.
    metadata = {
        # Used to build stable chunk ids.
        "document_id": "cancellation-policy",
        # Used for citations.
        "title": "Cancellation and Early Return Policy",
        # Used for filtering.
        "document_type": "policy",
        # Used for filtering.
        "department": "support",
        # Used for filtering.
        "audience": "customer",
        # Used for citations.
        "version": "v1.0",
        # Used for traceability.
        "source_path": "source.docx",
    }

    # Chunk the text with a small size so the test definitely creates chunks.
    chunks = semantic_chunk_text(text, metadata, chunk_size=300, chunk_overlap=50)

    # We expect more than one chunk because the sample text is repeated.
    assert len(chunks) > 1

    # Metadata should be copied onto the first chunk.
    assert chunks[0].metadata["title"] == "Cancellation and Early Return Policy"

    # Chunk id should start with the document id plus chunk marker.
    assert chunks[0].chunk_id.startswith("cancellation-policy:c")