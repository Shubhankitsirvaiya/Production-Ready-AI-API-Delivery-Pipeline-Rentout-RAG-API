from app.rag.chunking import semantic_chunk_text


def test_semantic_chunking_preserves_metadata() -> None:
    text = "\n".join(
        [
            "Cancellation Rules",
            "Customers may cancel before delivery when the route has not been dispatched.",
            "Active rental returns may require pickup and inspection before refund decisions.",
        ]
        * 10
    )
    metadata = {
        "document_id": "cancellation-policy",
        "title": "Cancellation and Early Return Policy",
        "document_type": "policy",
        "department": "support",
        "audience": "customer",
        "version": "v1.0",
        "source_path": "source.docx",
    }

    chunks = semantic_chunk_text(text, metadata, chunk_size=300, chunk_overlap=50)

    assert len(chunks) > 1
    assert chunks[0].metadata["title"] == "Cancellation and Early Return Policy"
    assert chunks[0].chunk_id.startswith("cancellation-policy:c")

