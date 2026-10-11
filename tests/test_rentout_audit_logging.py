from pathlib import Path

import pytest

from app.core.config import get_settings
from app.rag.audit import write_audit_event
from app.rag.schemas import AuditEvent


@pytest.mark.asyncio
async def test_write_audit_event_appends_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "audit_log_dir", tmp_path)

    await write_audit_event(
        AuditEvent(
            conversation_id="abc",
            question="Can I cancel?",
            status="success",
            latency_ms=42,
            retrieved_documents=["Cancellation Policy"],
        )
    )

    log_path = tmp_path / "chat_events.jsonl"
    assert log_path.exists()
    assert "Cancellation Policy" in log_path.read_text(encoding="utf-8")

