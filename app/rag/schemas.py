"""Pydantic request/response models for the RentOut API.

Schemas are the contract between clients, FastAPI, tests, and the RAG internals.
They validate inputs before business logic runs and make the generated OpenAPI
(`/docs`) page useful for demos and frontend integration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Input payload for POST /chat.

    question: User's natural-language question.
    customer_type: Lets the prompt adapt tone and policy framing.
    filters: Optional metadata filters for retrieval.
    top_k: Optional number of chunks to retrieve, capped to protect latency/cost.
    conversation_id: Optional client-provided id for multi-turn tracing.
    """

    question: str = Field(min_length=3, max_length=2000)
    customer_type: Literal["individual", "corporate", "support_agent"] = "individual"
    filters: dict[str, Any] | None = None
    top_k: int | None = Field(default=None, ge=1, le=10)
    conversation_id: str | None = None


class Citation(BaseModel):
    """Source evidence returned with each answer."""

    document: str
    section: str
    version: str
    source_path: str
    score: float


class ChatResponse(BaseModel):
    """Output payload for POST /chat."""

    conversation_id: str
    answer: str
    citations: list[Citation]
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    """Internal representation of one chunk returned by retrieval."""

    chunk_id: str
    text: str
    document_title: str
    section: str
    document_type: str
    department: str
    audience: str
    version: str
    source_path: str
    score: float


class AuditEvent(BaseModel):
    """One operational log event for a chat request."""

    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    conversation_id: str
    question: str
    status: Literal["success", "error"]
    latency_ms: int
    retrieved_documents: list[str] = Field(default_factory=list)
    error: str | None = None


class IngestResponse(BaseModel):
    """Response returned after rebuilding the vector store."""

    documents: int
    chunks: int
    vector_store_path: str