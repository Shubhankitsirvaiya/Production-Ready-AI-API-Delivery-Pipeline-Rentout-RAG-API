# Path is used for temporary audit log folders.
from pathlib import Path

# pytest provides async marker and monkeypatch fixture typing.
import pytest

# get_settings gives access to the cached settings object.
from app.core.config import get_settings

# write_audit_event is the function under test.
from app.rag.audit import write_audit_event

# AuditEvent defines the structured log payload.
from app.rag.schemas import AuditEvent


# Mark this test async because write_audit_event is async.
@pytest.mark.asyncio
async def test_write_audit_event_appends_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Get the cached settings object.
    settings = get_settings()

    # Redirect audit logs to a temporary folder so the real project is untouched.
    monkeypatch.setattr(settings, "audit_log_dir", tmp_path)

    # Write one audit event through the real function.
    await write_audit_event(
        AuditEvent(
            # Fake conversation id for traceability.
            conversation_id="abc",
            # Fake user question.
            question="Can I cancel?",
            # Mark the event as successful.
            status="success",
            # Fake latency value.
            latency_ms=42,
            # Fake retrieved source list.
            retrieved_documents=["Cancellation Policy"],
        )
    )

    # The function should write to this JSONL path.
    log_path = tmp_path / "chat_events.jsonl"

    # The audit file should now exist.
    assert log_path.exists()

    # The audit file should contain the retrieved source name.
    assert "Cancellation Policy" in log_path.read_text(encoding="utf-8")