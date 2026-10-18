"""Application configuration for the RentOut RAG service.

This module explains how the app reads runtime configuration. The main idea is:
source code should not contain secrets or machine-specific paths. Values like
`OPENAI_API_KEY`, model names, folder paths, and retrieval tuning parameters are
loaded from `.env` or environment variables.
"""

# Keep postponed type annotation behavior consistent across Python versions.
from __future__ import annotations

# lru_cache lets us create the Settings object once and reuse it everywhere.
from functools import lru_cache

# Path gives typed path objects instead of raw strings for local folders/files.
from pathlib import Path

# load_dotenv reads key=value pairs from the local `.env` file during dev.
from dotenv import load_dotenv

# BaseSettings maps environment variables onto a typed Python settings class.
from pydantic_settings import BaseSettings, SettingsConfigDict


# Load local `.env` values into the process environment before Settings is built.
load_dotenv()


# Settings is the single typed place where runtime configuration is declared.
class Settings(BaseSettings):
    """Typed runtime settings used by FastAPI, scripts, and the RAG modules."""

    # Human-readable app name shown in `/version` and FastAPI `/docs`.
    app_name: str = "RentOut RAG Chatbot"

    # Version value shown by `/version`; Docker builds override this via env var.
    app_version: str = "0.1.0"

    # OpenAI key is optional so tests can run without calling paid APIs.
    openai_api_key: str | None = None

    # Chat model used for final answer generation.
    openai_chat_model: str = "gpt-5"

    # Embedding model used for both document chunks and user questions.
    openai_embedding_model: str = "text-embedding-3-small"

    # LangSmith remains opt-in because traces can contain application content.
    langsmith_tracing: bool = False

    # Optional LangSmith credential; it is never returned by an API endpoint.
    langsmith_api_key: str | None = None

    # Logical trace collection name used only when tracing is enabled.
    langsmith_project: str = "rentout-local-development"

    # LangSmith endpoint can be changed for regional accounts.
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    # Environment label used to distinguish local, dev, test, and prod.
    deployment_environment: str = "local"

    # Kubernetes Downward API replaces these defaults inside a Pod.
    pod_name: str = "local-process"
    pod_namespace: str = "local"
    node_name: str = "local-machine"

    # Minimum severity used by application logging.
    log_level: str = "INFO"

    # Root folder for all local demo data.
    data_dir: Path = Path("app/data")

    # Folder containing markdown prompt templates.
    prompt_dir: Path = Path("app/data/prompts")

    # Folder where JSONL audit events are written.
    audit_log_dir: Path = Path("app/data/audit_logs")

    # Local JSON file that stores chunk text, metadata, and embeddings.
    vector_store_path: Path = Path("app/data/vector_store/rentout_vectors.json")

    # Default number of retrieved chunks sent to the answer model.
    top_k: int = 5

    # Approximate character budget for each retrievable text chunk.
    chunk_size: int = 900

    # Number of trailing characters repeated into the next chunk.
    chunk_overlap: int = 150

    # Tell Pydantic to read `.env`, use UTF-8, and ignore unrelated env vars.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# Cache the Settings object so every import sees one consistent config snapshot.
@lru_cache
def get_settings() -> Settings:
    """Return the app settings object used by the whole process."""

    # Instantiating Settings reads environment variables and applies defaults.
    return Settings()
