"""Audit logging for chatbot requests.

Every production AI system should preserve enough trace data to answer basic
questions later: what was asked, whether the call succeeded, how long it took,
and which documents were used. This demo stores that information in JSONL.
"""

from __future__ import annotations

import asyncio
import json

from app.core.config import get_settings
from app.rag.schemas import AuditEvent


async def write_audit_event(event: AuditEvent) -> None:
    """Append one request event to `chat_events.jsonl` asynchronously.

    JSONL means one JSON object per line. It is simple, append-friendly, and easy
    to inspect with command-line tools. In production, this same boundary could
    send events to CloudWatch, Datadog, ELK, or a warehouse ingestion queue.
    """
    settings = get_settings()
    settings.audit_log_dir.mkdir(parents=True, exist_ok=True)
    log_path = settings.audit_log_dir / "chat_events.jsonl"
    payload = event.model_dump()

    def _append() -> None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    # Local file writes are blocking, so run them in a thread to keep the async
    # API responsive under concurrent traffic.
    await asyncio.to_thread(_append)