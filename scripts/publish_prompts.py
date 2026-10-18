"""Publish every local RentOut markdown prompt to private LangSmith storage.

Run from the repository root after editing a prompt:

    python -m scripts.publish_prompts

The command reads credentials from the ignored `.env` file. It never prints or
writes the LangSmith API key.
"""

# Keep annotations future-compatible.
from __future__ import annotations

# PromptTemplate is the versioned object serialized by LangSmith.
from langchain_core.prompts import PromptTemplate

# Client performs authenticated prompt create/update operations.
from langsmith import Client

# Settings provide the local directory, endpoint, key, and naming prefix.
from app.core.config import get_settings


def main() -> None:
    """Publish all `.md` files in PROMPT_DIR as private managed prompts."""

    # Read configuration once so the complete publication uses one account.
    settings = get_settings()

    # Fail before scanning files when credentials are not configured.
    if not settings.langsmith_api_key:
        raise RuntimeError("LANGSMITH_API_KEY is required to publish prompts.")

    # Connect to the account and regional endpoint selected in `.env`.
    client = Client(
        api_url=settings.langsmith_endpoint,
        api_key=settings.langsmith_api_key,
    )

    # Sort files so repeated publication produces predictable console output.
    prompt_paths = sorted(settings.prompt_dir.glob("*.md"))

    # An empty registry likely indicates a path mistake, so fail clearly.
    if not prompt_paths:
        raise FileNotFoundError(f"No markdown prompts found in {settings.prompt_dir}")

    # Publish each local logical prompt as one private LangSmith prompt.
    for prompt_path in prompt_paths:
        # Convert customer_chat.md into customer-chat for the remote name.
        normalized_name = prompt_path.stem.replace("_", "-")
        prompt_identifier = f"{settings.langsmith_prompt_prefix}-{normalized_name}"

        # Read the reviewed source text and wrap it as a serializable template.
        prompt_text = prompt_path.read_text(encoding="utf-8")
        prompt_object = PromptTemplate.from_template(prompt_text)

        # push_prompt creates the prompt or adds a commit when it already exists.
        prompt_url = client.push_prompt(
            prompt_identifier,
            object=prompt_object,
            is_public=False,
            description=f"Managed system prompt for RentOut: {prompt_path.stem}",
            tags=["rentout", "production-api", "managed-prompt"],
        )

        # Print only the safe identifier and returned management URL.
        print(f"Published {prompt_identifier}: {prompt_url}")


# Execute publication only when invoked as a module or script.
if __name__ == "__main__":
    main()
