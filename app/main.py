"""FastAPI application entrypoint.

`uvicorn app.main:app --reload` imports this module and looks for the `app`
object. Keeping the entrypoint thin makes deployment predictable: the routes own
API behavior, the RAG package owns retrieval/generation logic, and this file only
assembles the service.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.core.config import get_settings


settings = get_settings()

# These values appear in /docs. In a production API, useful OpenAPI metadata
# helps frontend developers, QA engineers, and platform teams test the service.
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Async RAG chatbot for RentOut furniture rental policies.",
)

# Routes are grouped by responsibility. Health/version endpoints support
# deployment checks, while chat/ingest endpoints implement the RAG product flow.
app.include_router(health_router)
app.include_router(chat_router)