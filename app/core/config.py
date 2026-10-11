"""Application configuration for the RentOut RAG service.

This file is intentionally small, but it is one of the most important files
for a production-style project. Instead of hardcoding secrets, paths, model
names, and tuning values inside route code, every runtime setting is read from
`.env` or environment variables.

Why this matters in deployment:
- Local development can use `.env`.
- Docker Compose can inject the same values into the container.
- CI/CD and cloud platforms can provide secrets without committing them to git.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


# Load key=value pairs from `.env` into process environment variables.
# Pydantic will then map those environment variables onto the Settings class.
load_dotenv()


class Settings(BaseSettings):
    """Typed runtime settings used by the FastAPI app and RAG pipeline.

    Each field has a safe default so tests can run without a real `.env`, while
    sensitive values such as OPENAI_API_KEY can be provided privately at runtime.
    """

    # Service metadata exposed by /version and OpenAPI docs.
    app_name: str = "RentOut RAG Chatbot"
    app_version: str = "0.1.0"

    # Secret used by OpenAI SDK calls. This must live in `.env` or deployment
    # secrets, never in source code.
    openai_api_key: str | None = None

    # Model names are configuration because production teams often change model
    # versions without changing application logic.
    openai_chat_model: str = "gpt-5"
    openai_embedding_model: str = "text-embedding-3-small"

    # Local folders are used now to make the project easy to demo. The rest of
    # the code treats them as boundaries that can later become S3, LangSmith,
    # a managed vector DB, or an external audit service.
    data_dir: Path = Path("app/data")
    prompt_dir: Path = Path("app/data/prompts")
    audit_log_dir: Path = Path("app/data/audit_logs")
    vector_store_path: Path = Path("app/data/vector_store/rentout_vectors.json")

    # Retrieval controls:
    # top_k controls how many chunks are passed to the answer model.
    # chunk_size controls the approximate character budget per chunk.
    # chunk_overlap keeps context continuity between neighboring chunks.
    top_k: int = 5
    chunk_size: int = 900
    chunk_overlap: int = 150

    # extra="ignore" lets this project share a machine with other `.env` keys
    # without failing validation. That is useful in teaching and multi-project
    # folders where unrelated settings may already exist.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return one cached Settings object per Python process.

    FastAPI imports this function in many modules. Caching avoids repeatedly
    parsing `.env` and gives the app a single consistent configuration snapshot.
    """
    return Settings()