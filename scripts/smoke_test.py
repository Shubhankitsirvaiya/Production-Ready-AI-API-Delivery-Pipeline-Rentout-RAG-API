"""Small async smoke test for a running local API.

This script is useful after starting the API. It hits real HTTP endpoints, so it
checks the running service rather than importing Python functions directly.
"""

# Keep annotations future-compatible.
from __future__ import annotations

# asyncio.run starts the async smoke test from a normal script.
import asyncio

# httpx.AsyncClient makes non-blocking HTTP requests.
import httpx


# main is async because HTTP calls are network I/O.
async def main() -> None:
    # Create an HTTP client pointed at the local FastAPI server.
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30) as client:
        # Call /health to confirm the API process is alive.
        health = await client.get("/health")

        # Print the status code and JSON response for quick visual feedback.
        print("health", health.status_code, health.json())

        # Call /chat with a sample RentOut question.
        chat = await client.post(
            # Target endpoint.
            "/chat",
            # JSON payload matching ChatRequest.
            json={"question": "Can I cancel my sofa rental after delivery?", "customer_type": "individual"},
        )

        # Print the chat response so we can confirm end-to-end behavior.
        print("chat", chat.status_code, chat.json())


# This block runs only when the script is executed directly.
if __name__ == "__main__":
    # Start the event loop and run the async smoke test.
    asyncio.run(main())