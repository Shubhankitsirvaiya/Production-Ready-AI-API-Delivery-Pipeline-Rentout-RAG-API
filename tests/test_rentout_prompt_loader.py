from pathlib import Path

import pytest

from app.core.config import get_settings
from app.rag.prompt_loader import load_prompt


@pytest.mark.asyncio
async def test_load_prompt_reads_local_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "customer_chat.md").write_text("Answer from policy context.", encoding="utf-8")

    settings = get_settings()
    monkeypatch.setattr(settings, "prompt_dir", prompt_dir)

    prompt = await load_prompt("customer_chat")
    assert "policy context" in prompt


@pytest.mark.asyncio
async def test_load_prompt_fails_clearly_for_missing_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "prompt_dir", tmp_path)

    with pytest.raises(FileNotFoundError):
        await load_prompt("missing")

