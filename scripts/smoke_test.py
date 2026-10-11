"""Small async smoke test for a running local API.

Use this after starting FastAPI to prove the service responds end-to-end:

    python -m uvicorn app.main:app --reload
    python scripts/smoke_test.py

This is not a replacement for pytest. It is a deployment sanity check that hits
real HTTP endpoints the same way a client would.
"""

from __future__ import annotations

import asyncio

import httpx


async def main() -> None:
    # AsyncClient keeps the same async pattern used by the API: network calls are
    # awaited instead of blocking the event loop.
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30) as client:
        health = await client.get("/health")
        print("health", health.status_code, health.json())
        chat = await client.post(
            "/chat",
            json={"question": "Can I cancel my sofa rental after delivery?", "customer_type": "individual"},
        )
        print("chat", chat.status_code, chat.json())


if __name__ == "__main__":
    asyncio.run(main())