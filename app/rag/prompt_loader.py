"""Prompt registry access.

Prompts live in `app/data/prompts` today so the project is easy to run locally.
The function is async and isolated because in a production setup the same call
could later fetch prompts from LangSmith, a database, or a config service.
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings


async def load_prompt(prompt_name: str) -> str:
    """Load a named markdown prompt.

    Arguments:
    - prompt_name: File stem inside the prompt directory. For example,
      `customer_chat` maps to `app/data/prompts/customer_chat.md`.
    """
    settings = get_settings()
    prompt_path = settings.prompt_dir / f"{prompt_name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")

    # File reads are small here, but using to_thread teaches the same pattern we
    # would use for slower prompt registries: don't block the event loop.
    return await asyncio.to_thread(prompt_path.read_text, encoding="utf-8")