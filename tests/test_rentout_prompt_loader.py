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

    # Missing prompt files should raise FileNotFoundError.
    with pytest.raises(FileNotFoundError):
        # Try loading a prompt that does not exist.
        await load_prompt("missing")