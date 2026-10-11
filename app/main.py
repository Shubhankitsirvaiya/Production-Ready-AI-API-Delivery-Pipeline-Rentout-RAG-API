"""FastAPI application entrypoint.

Uvicorn loads `app.main:app`. This file keeps startup simple: read settings,
create the FastAPI object, and attach route groups.
"""

# Keep type annotations future-compatible.
from __future__ import annotations

# FastAPI is the web framework used to expose the API.
from fastapi import FastAPI

# Chat router contains `/chat` and `/ingest`.
from app.api.routes_chat import router as chat_router

# Health router contains `/health` and `/version`.
from app.api.routes_health import router as health_router

# get_settings reads app name/version from `.env` or environment variables.
from app.core.config import get_settings


# Build the settings object once at import time for application metadata.
settings = get_settings()

# Create the FastAPI application object that Uvicorn will serve.
app = FastAPI(
    # Title appears on the generated Swagger UI page at `/docs`.
    title=settings.app_name,
    # Version also appears in OpenAPI metadata.
    version=settings.app_version,
    # Description explains the API purpose to humans reading `/docs`.
    description="Async RAG chatbot for RentOut furniture rental policies.",
)

# Register system endpoints such as `/health` and `/version`.
app.include_router(health_router)

# Register product endpoints such as `/chat` and `/ingest`.
app.include_router(chat_router)