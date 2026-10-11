"""System endpoints used by humans, Docker, and CI/CD checks."""

# Keep annotation handling consistent.
from __future__ import annotations

# APIRouter groups related FastAPI endpoints before they are attached in main.py.
from fastapi import APIRouter

# Settings provide app name and app version for `/version`.
from app.core.config import get_settings


# Tag groups these routes under "system" in Swagger UI.
router = APIRouter(tags=["system"])


# Register a GET endpoint at `/health`.
@router.get("/health")
async def health() -> dict[str, str]:
    """Return a minimal liveness response."""

    # Keep this endpoint cheap: no OpenAI calls, no vector store, no file reads.
    return {"status": "ok"}


# Register a GET endpoint at `/version`.
@router.get("/version")
async def version() -> dict[str, str]:
    """Return application identity and version metadata."""

    # Read current settings so Docker-provided APP_VERSION is reflected here.
    settings = get_settings()

    # Return a stable JSON contract for demos and release verification.
    return {"app": settings.app_name, "version": settings.app_version}