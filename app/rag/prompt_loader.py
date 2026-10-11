"""Prompt registry access.

Prompts are local markdown files today. The function is async so this boundary can
later move to LangSmith or another prompt service without changing route code.
"""

# Keep annotations future-compatible.
from __future__ import annotations

# asyncio.to_thread lets local file reading avoid blocking the event loop.
import asyncio

# Settings provide the prompt directory path.
from app.core.config import get_settings


async def load_prompt(prompt_name: str) -> str:
    """Load a named markdown prompt."""

    # Read runtime settings.
    settings = get_settings()

    # Convert logical prompt name into an actual markdown file path.
    prompt_path = settings.prompt_dir / f"{prompt_name}.md"

    # Fail clearly if the prompt registry does not contain the requested file.
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")

    # Read file contents in a worker thread so FastAPI's event loop is not blocked.
    return await asyncio.to_thread(prompt_path.read_text, encoding="utf-8")