"""System endpoints used by humans, Docker, and CI/CD checks."""

# Keep annotation handling consistent.
from __future__ import annotations

# APIRouter groups related FastAPI endpoints before they are attached in main.py.
from fastapi import APIRouter, Response, status

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


# Kubernetes calls this endpoint before routing Service traffic to a Pod.
@router.get("/ready")
async def ready(response: Response) -> dict[str, str | bool]:
    """Report whether retrieval data exists and the Pod can serve chat traffic."""

    # Read the configured path, which points to the PVC inside Kubernetes.
    settings = get_settings()

    # A non-empty vector store is required by every real retrieval request.
    vector_store_ready = settings.vector_store_path.is_file() and settings.vector_store_path.stat().st_size > 0

    # A 503 keeps the Pod alive but removes it from the Service endpoint list.
    if not vector_store_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # Return a small diagnostic body for Headlamp and manual checks.
    return {"status": "ready" if vector_store_ready else "not_ready", "vector_store": vector_store_ready}


# Register a GET endpoint at `/version`.
@router.get("/version")
async def version() -> dict[str, str]:
    """Return application identity and version metadata."""

    # Read current settings so Docker-provided APP_VERSION is reflected here.
    settings = get_settings()

    # Return a stable JSON contract for demos and release verification.
    return {"app": settings.app_name, "version": settings.app_version}


# This safe status endpoint helps demonstrate traffic moving between Pod versions.
@router.get("/ops/status")
async def operations_status() -> dict[str, str | bool]:
    """Return non-secret runtime and deployment identity."""

    settings = get_settings()

    return {
        "environment": settings.deployment_environment,
        "pod_name": settings.pod_name,
        "pod_namespace": settings.pod_namespace,
        "node_name": settings.node_name,
        "app_version": settings.app_version,
        # Report configured state only; never expose the LangSmith API key.
        "langsmith_tracing": settings.langsmith_tracing and bool(settings.langsmith_api_key),
        "langsmith_project": settings.langsmith_project,
    }
