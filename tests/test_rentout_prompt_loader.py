# Path is used for pytest temporary folders.
from pathlib import Path

# pytest provides async test marker and monkeypatch fixture typing.
import pytest

# get_settings returns the cached settings object used by the app.
from app.core.config import get_settings

# load_prompt is the function under test.
from app.rag.prompt_loader import load_prompt


# Mark this test async because load_prompt is async.
@pytest.mark.asyncio
async def test_load_prompt_reads_local_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Create a temporary prompt directory isolated from real project files.
    prompt_dir = tmp_path / "prompts"

    # Ensure the temporary directory exists.
    prompt_dir.mkdir()

    # Write a fake prompt file into the temporary registry.
    (prompt_dir / "customer_chat.md").write_text("Answer from policy context.", encoding="utf-8")

    # Get the cached settings object.
    settings = get_settings()

    # Redirect prompt_dir to the temporary folder for this test only.
    monkeypatch.setattr(settings, "prompt_dir", prompt_dir)

    # Force offline mode so this unit test never contacts LangSmith.
    monkeypatch.setattr(settings, "prompt_source", "local")

    # Load the fake prompt through the real function.
    prompt = await load_prompt("customer_chat")

    # Confirm the prompt contents were read.
    assert "policy context" in prompt


# Mark this test async because load_prompt is async.
@pytest.mark.asyncio
async def test_load_prompt_fails_clearly_for_missing_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Get the cached settings object.
    settings = get_settings()

    # Point prompt_dir to an empty temporary directory.
    monkeypatch.setattr(settings, "prompt_dir", tmp_path)

    # Force local mode so the missing-file behavior is isolated.
    monkeypatch.setattr(settings, "prompt_source", "local")

    # Missing prompt files should raise FileNotFoundError.
    with pytest.raises(FileNotFoundError):
        # Try loading a prompt that does not exist.
        await load_prompt("missing")


# Verify that deployed mode prefers the managed LangSmith prompt.
@pytest.mark.asyncio
async def test_load_prompt_reads_langsmith_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    # Import the module so its blocking pull helper can be replaced safely.
    from app.rag import prompt_loader

    # Select the deployed prompt source and require remote success.
    settings = get_settings()
    monkeypatch.setattr(settings, "prompt_source", "langsmith")
    monkeypatch.setattr(settings, "prompt_local_fallback", False)

    # Replace network I/O with a deterministic private-registry response.
    monkeypatch.setattr(
        prompt_loader,
        "_pull_langsmith_prompt",
        lambda prompt_name: f"Managed prompt: {prompt_name}",
    )

    # The public async boundary should return the remotely managed prompt.
    prompt = await load_prompt("customer_chat")

    assert prompt == "Managed prompt: customer_chat"


# Verify resilience when the external prompt service is unavailable.
@pytest.mark.asyncio
async def test_load_prompt_falls_back_when_langsmith_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Create an isolated packaged fallback prompt.
    (tmp_path / "customer_chat.md").write_text("Fallback policy prompt.", encoding="utf-8")

    # Enable LangSmith-first behavior with the local continuity fallback.
    settings = get_settings()
    monkeypatch.setattr(settings, "prompt_dir", tmp_path)
    monkeypatch.setattr(settings, "prompt_source", "langsmith")
    monkeypatch.setattr(settings, "prompt_local_fallback", True)

    # Simulate a registry outage without making a real network request.
    from app.rag import prompt_loader

    def fail_pull(prompt_name: str) -> str:
        raise ConnectionError(f"Registry unavailable for {prompt_name}")

    monkeypatch.setattr(prompt_loader, "_pull_langsmith_prompt", fail_pull)

    # The request should continue using the reviewed packaged prompt.
    prompt = await load_prompt("customer_chat")

    assert prompt == "Fallback policy prompt."
