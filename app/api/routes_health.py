"""System endpoints used by humans, tests, Docker, and CI/CD checks."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings


router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Return a tiny liveness response.

    Docker, load balancers, and CI smoke tests usually need a cheap endpoint
    that proves the API process is running without calling OpenAI or reading the
    vector store.
    """
    return {"status": "ok"}


@router.get("/version")
async def version() -> dict[str, str]:
    """Expose deployable version metadata.

    This is useful when testing image versioning: after a Docker image is built
    from a commit SHA or tag, the running service can confirm what app version it
    contains.
    """
    settings = get_settings()
    return {"app": settings.app_name, "version": settings.app_version}