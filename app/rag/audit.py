"""Audit logging for chatbot requests."""

# Keep annotations future-compatible.
from __future__ import annotations

# asyncio.to_thread lets local file writes happen outside the event loop.
import asyncio

# json serializes Pydantic audit data into JSONL records.
import json

# Settings provide the audit log directory.
from app.core.config import get_settings

# AuditEvent defines the exact fields written to logs.
from app.rag.schemas import AuditEvent


async def write_audit_event(event: AuditEvent) -> None:
    """Append one request event to `chat_events.jsonl` asynchronously."""

    # Read runtime settings.
    settings = get_settings()

    # Ensure the audit log folder exists before writing.
    settings.audit_log_dir.mkdir(parents=True, exist_ok=True)

    # Store all chat events in one JSONL file.
    log_path = settings.audit_log_dir / "chat_events.jsonl"

    # Convert the Pydantic model into a plain dictionary.
    payload = event.model_dump()

    # Define a synchronous append function because normal file I/O is blocking.
    def _append() -> None:
        # Open the log in append mode so existing events are preserved.
        with log_path.open("a", encoding="utf-8") as handle:
            # Write one compact JSON object per line.
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    # Run the blocking file append in a worker thread.
    await asyncio.to_thread(_append)