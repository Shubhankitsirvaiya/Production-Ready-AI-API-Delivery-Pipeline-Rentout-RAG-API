"""CLI entrypoint for rebuilding the local vector store.

Run this when source DOCX files change:

    python scripts/ingest_docs.py

It calls the same ingestion function used by POST /ingest, which keeps demo and
API behavior aligned.
"""

from __future__ import annotations

import asyncio

from app.scripts_api import ingest_documents


async def main() -> None:
    response = await ingest_documents()
    print(response.model_dump())


if __name__ == "__main__":
    asyncio.run(main())