"""CLI entrypoint for rebuilding the local vector store.

Run this when RentOut source documents change:

    python scripts/ingest_docs.py
"""

# Keep annotations future-compatible.
from __future__ import annotations

# asyncio.run starts the async ingestion function from a normal script.
import asyncio

# Shared ingestion function also used by POST /ingest.
from app.scripts_api import ingest_documents


# main is async because ingestion calls OpenAI embeddings and async file helpers.
async def main() -> None:
    # Run the shared ingestion pipeline.
    response = await ingest_documents()

    # Print a JSON-like summary for the developer running the command.
    print(response.model_dump())


# This block runs only when the file is executed directly.
if __name__ == "__main__":
    # Start the event loop and execute main().
    asyncio.run(main())