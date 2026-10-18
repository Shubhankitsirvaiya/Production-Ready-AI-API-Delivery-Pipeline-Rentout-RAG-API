"""Asynchronous access to the managed RentOut prompt registry.

LangSmith is the primary runtime source in deployed environments. Packaged
markdown remains a deliberate fallback so a prompt-service outage does not make
the customer-support API unavailable.
"""

# Keep annotations future-compatible.
from __future__ import annotations

# asyncio.to_thread moves blocking SDK and filesystem work off FastAPI's loop.
import asyncio

# Standard logging records when the resilience fallback is used.
import logging

# LangSmith Client provides private prompt pull and versioning operations.
from langsmith import Client

# Settings define source selection, credentials, naming, and fallback policy.
from app.core.config import get_settings


# Use this module's name so log collectors can filter prompt-registry events.
logger = logging.getLogger(__name__)


def _prompt_identifier(prompt_name: str) -> str:
    """Map a local logical name to a private LangSmith prompt identifier."""

    # Read the cached settings used by the rest of the application.
    settings = get_settings()

    # LangSmith names use hyphens while Python-facing names use underscores.
    normalized_name = prompt_name.replace("_", "-")

    # Prefix prevents collisions with prompts owned by other applications.
    identifier = f"{settings.langsmith_prompt_prefix}-{normalized_name}"

    # A commit suffix pins an immutable version; blank follows latest.
    if settings.langsmith_prompt_commit:
        identifier = f"{identifier}:{settings.langsmith_prompt_commit}"

    return identifier


def _pull_langsmith_prompt(prompt_name: str) -> str:
    """Perform the blocking LangSmith SDK request in a worker thread."""

    # Read connection settings without exposing their values in logs.
    settings = get_settings()

    # Prompt retrieval requires a LangSmith API key.
    if not settings.langsmith_api_key:
        raise RuntimeError("LANGSMITH_API_KEY is required when PROMPT_SOURCE=langsmith.")

    # Use the configured regional endpoint and private account credential.
    client = Client(
        api_url=settings.langsmith_endpoint,
        api_key=settings.langsmith_api_key,
    )

    # Pull only the prompt template. include_model=False prevents remote model
    # configuration or credentials from becoming executable runtime settings.
    prompt_object = client.pull_prompt(
        _prompt_identifier(prompt_name),
        include_model=False,
    )

    # The publishing script stores a PromptTemplate with no input variables.
    if getattr(prompt_object, "input_variables", None):
        raise ValueError("Managed system prompts must not require input variables.")

    # Render the template into the plain system string expected by generator.py.
    return prompt_object.format()


def _read_local_prompt(prompt_name: str) -> str:
    """Read the packaged fallback prompt from the local registry."""

    # Resolve the logical prompt name under the configured local directory.
    prompt_path = get_settings().prompt_dir / f"{prompt_name}.md"

    # Raise a useful error when neither registry contains the requested prompt.
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")

    # Explicit UTF-8 keeps behavior consistent across Windows and Linux.
    return prompt_path.read_text(encoding="utf-8")


async def load_prompt(prompt_name: str) -> str:
    """Load a prompt asynchronously from LangSmith or the local registry."""

    # Read source selection once for this request.
    settings = get_settings()

    # Offline development can explicitly bypass all network access.
    if settings.prompt_source == "local":
        return await asyncio.to_thread(_read_local_prompt, prompt_name)

    try:
        # The LangSmith prompt API is synchronous, so to_thread keeps FastAPI's
        # event loop free to serve health checks and concurrent requests.
        return await asyncio.to_thread(_pull_langsmith_prompt, prompt_name)
    except Exception:
        # Strict environments can disable fallback and surface registry errors.
        if not settings.prompt_local_fallback:
            raise

        # Log the fallback without including prompt content or secret values.
        logger.exception(
            "LangSmith prompt pull failed; using packaged fallback",
            extra={"prompt_name": prompt_name},
        )

        # File I/O also runs in a worker thread for event-loop hygiene.
        return await asyncio.to_thread(_read_local_prompt, prompt_name)
