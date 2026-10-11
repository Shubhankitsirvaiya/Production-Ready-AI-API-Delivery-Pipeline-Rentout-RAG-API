"""Pydantic models for API contracts and internal RAG data.

Pydantic models are important because they make the API explicit. FastAPI uses
these classes to validate requests, serialize responses, and generate `/docs`.
"""

# Keep type annotations future-compatible.
from __future__ import annotations

# datetime/timezone let audit events get a UTC timestamp by default.
from datetime import datetime, timezone

# Any supports flexible filter/metadata dictionaries; Literal restricts strings.
from typing import Any, Literal

# BaseModel is the Pydantic base class; Field adds validation/default metadata.
from pydantic import BaseModel, Field


# ChatRequest is the JSON body accepted by POST /chat.
class ChatRequest(BaseModel):
    """Input payload for POST /chat."""

    # The user question must be meaningful but bounded to protect the API.
    question: str = Field(min_length=3, max_length=2000)

    # Customer type is restricted to known values so prompts can branch safely.
    customer_type: Literal["individual", "corporate", "support_agent"] = "individual"

    # Optional retrieval filters, such as department or audience.
    filters: dict[str, Any] | None = None

    # Optional per-request top-k override, capped between 1 and 10.
    top_k: int | None = Field(default=None, ge=1, le=10)

    # Optional client-provided id so multiple calls can be tied together.
    conversation_id: str | None = None


# Citation is the source-evidence object returned to the caller.
class Citation(BaseModel):
    """Source evidence returned with each answer."""

    # Human-readable document title.
    document: str

    # Section inside the source document/chunk.
    section: str

    # Source document version for review and governance.
    version: str

    # Local path to the source file in this demo project.
    source_path: str

    # Retrieval similarity score.
    score: float


# ChatResponse is the JSON body returned by POST /chat.
class ChatResponse(BaseModel):
    """Output payload for POST /chat."""

    # Id used to correlate answer, audit logs, and client session.
    conversation_id: str

    # Final generated answer text.
    answer: str

    # Evidence list built from retrieval metadata.
    citations: list[Citation]

    # Extra diagnostics such as retrieved chunk count.
    metadata: dict[str, Any] = Field(default_factory=dict)


# RetrievedChunk is used inside the backend after retrieval.
class RetrievedChunk(BaseModel):
    """Internal representation of one chunk returned by retrieval."""

    # Stable chunk identifier, such as document-id:c1.
    chunk_id: str

    # Text that will be sent to the LLM as grounding context.
    text: str

    # Source document title.
    document_title: str

    # Source section heading or fallback label.
    section: str

    # Type of source document, such as policy or agreement.
    document_type: str

    # Department responsible for the document.
    department: str

    # Intended audience, such as customer or support_agent.
    audience: str

    # Source document version.
    version: str

    # Path to the source file.
    source_path: str

    # Cosine similarity score from retrieval.
    score: float


# AuditEvent is written to JSONL after every chat request.
class AuditEvent(BaseModel):
    """One operational log event for a chat request."""

    # Use UTC timestamp automatically when the event object is created.
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Store conversation id for traceability.
    conversation_id: str

    # Store the question that was asked.
    question: str

    # Restrict status to success/error so logs stay consistent.
    status: Literal["success", "error"]

    # Store route latency in milliseconds.
    latency_ms: int

    # Store retrieved document titles for successful responses.
    retrieved_documents: list[str] = Field(default_factory=list)

    # Store exception message for failed responses.
    error: str | None = None


# IngestResponse is returned by POST /ingest and the CLI ingestion script.
class IngestResponse(BaseModel):
    """Response returned after rebuilding the vector store."""

    # Number of DOCX files read.
    documents: int

    # Number of chunks produced across all documents.
    chunks: int

    # Path where the vector store JSON was written.
    vector_store_path: str