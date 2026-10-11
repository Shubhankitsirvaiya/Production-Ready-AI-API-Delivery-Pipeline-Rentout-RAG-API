"""RAG API routes.

This module is the main request workflow. FastAPI receives a user question,
starts independent I/O concurrently, generates an answer from retrieved context,
returns citations, and writes an audit event.
"""

# Keep type annotations future-compatible.
from __future__ import annotations

# asyncio gives us create_task and gather for concurrent I/O work.
import asyncio

# time.perf_counter measures request latency accurately.
import time

# uuid4 creates a unique conversation id when the client does not provide one.
from uuid import uuid4

# APIRouter registers endpoints; HTTPException returns API-friendly errors.
from fastapi import APIRouter, HTTPException

# write_audit_event stores success/error traces for reviewability.
from app.rag.audit import write_audit_event

# generate_answer calls OpenAI or local fallback answer generation.
from app.rag.generator import generate_answer

# load_prompt reads a prompt from the local prompt registry.
from app.rag.prompt_loader import load_prompt

# retrieve_context finds relevant RentOut policy chunks.
from app.rag.retriever import retrieve_context

# Pydantic schemas define request, response, citation, and audit shapes.
from app.rag.schemas import AuditEvent, ChatRequest, ChatResponse, Citation, IngestResponse

# ingest_documents lets the API rebuild the vector store through POST /ingest.
from app.scripts_api import ingest_documents


# Group chat/RAG endpoints under the "rag" Swagger tag.
router = APIRouter(tags=["rag"])


# POST /chat accepts a ChatRequest body and returns a ChatResponse body.
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Answer a customer/support question using retrieved RentOut policies."""

    # Capture start time so we can record latency in the audit log.
    started = time.perf_counter()

    # Use the provided conversation id, or create a new one for traceability.
    conversation_id = request.conversation_id or str(uuid4())

    # Use try/except so both successful and failed requests are audited.
    try:
        # Start prompt loading immediately without waiting for retrieval first.
        prompt_task = asyncio.create_task(load_prompt("customer_chat"))

        # Start retrieval immediately because it is independent from prompt loading.
        context_task = asyncio.create_task(retrieve_context(request.question, request.filters, request.top_k))

        # Wait for both tasks to finish and unpack results in task order.
        system_prompt, chunks = await asyncio.gather(prompt_task, context_task)

        # Generate the final answer from the prompt, request, and retrieved chunks.
        answer = await generate_answer(system_prompt=system_prompt, request=request, chunks=chunks)

        # Convert each retrieved chunk into a public citation object.
        citations = [
            # Citation intentionally uses retriever metadata, not LLM-generated text.
            Citation(
                # Document title shown to the user.
                document=chunk.document_title,
                # Section label inferred during chunking.
                section=chunk.section,
                # Source document version for governance/review.
                version=chunk.version,
                # Local source path for demo traceability.
                source_path=chunk.source_path,
                # Similarity score produced by retrieval.
                score=chunk.score,
            )
            # Repeat this conversion for every chunk returned by retrieval.
            for chunk in chunks
        ]

        # Build the structured response that FastAPI serializes to JSON.
        response = ChatResponse(
            # Return the id so callers can connect requests in logs.
            conversation_id=conversation_id,
            # Return the generated or fallback answer text.
            answer=answer,
            # Return citations so the answer is reviewable.
            citations=citations,
            # Return extra operational metadata for demos/debugging.
            metadata={
                # Show how many chunks were retrieved.
                "retrieved_chunks": len(chunks),
                # Explain the async pattern used in the route.
                "async_pattern": "prompt loading and context retrieval run concurrently",
            },
        )

        # Convert elapsed seconds into integer milliseconds for audit logs.
        latency_ms = int((time.perf_counter() - started) * 1000)

        # Write a success event to the local JSONL audit log.
        await write_audit_event(
            AuditEvent(
                # Store the conversation id used by this response.
                conversation_id=conversation_id,
                # Store the original user question for traceability.
                question=request.question,
                # Mark the request as successful.
                status="success",
                # Store total request latency.
                latency_ms=latency_ms,
                # Store which documents were retrieved.
                retrieved_documents=[chunk.document_title for chunk in chunks],
            )
        )

        # Return the final API response to the client.
        return response

    # Catch unexpected failures so the API returns a proper 500 and logs context.
    except Exception as exc:
        # Measure latency even for failed requests.
        latency_ms = int((time.perf_counter() - started) * 1000)

        # Write an error event to the audit log for later debugging.
        await write_audit_event(
            AuditEvent(
                # Keep the same conversation id for the failed request.
                conversation_id=conversation_id,
                # Store the user question that caused the failure.
                question=request.question,
                # Mark the request as an error.
                status="error",
                # Store how long the failed request ran.
                latency_ms=latency_ms,
                # Store the exception message for debugging.
                error=str(exc),
            )
        )

        # Convert the Python exception into an HTTP 500 response.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# POST /ingest lets a user rebuild the vector store from DOCX files.
@router.post("/ingest", response_model=IngestResponse)
async def ingest() -> IngestResponse:
    """Build the local vector store from the RentOut DOCX policy corpus."""

    # Delegate to shared ingestion logic so API and CLI behavior stay identical.
    return await ingest_documents()