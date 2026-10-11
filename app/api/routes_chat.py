"""RAG API routes.

This module shows the production pattern the project is meant to teach:
FastAPI receives a request, starts independent I/O work concurrently, generates
a grounded answer from retrieved context, and writes an audit event.
"""

from __future__ import annotations

import asyncio
import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.rag.audit import write_audit_event
from app.rag.generator import generate_answer
from app.rag.prompt_loader import load_prompt
from app.rag.retriever import retrieve_context
from app.rag.schemas import AuditEvent, ChatRequest, ChatResponse, Citation, IngestResponse
from app.scripts_api import ingest_documents


router = APIRouter(tags=["rag"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Answer a customer/support question using retrieved RentOut policies.

    Step-by-step:
    1. Create or reuse a conversation id for traceability.
    2. Start prompt loading and vector retrieval at the same time.
    3. Wait for both async tasks, then call the answer model.
    4. Convert retrieved chunks into citations for transparency.
    5. Write a local audit event so the request can be reviewed later.
    """
    started = time.perf_counter()
    conversation_id = request.conversation_id or str(uuid4())

    try:
        # These two operations are independent. The prompt can be loaded while
        # the query embedding/vector search is happening. In real production,
        # the prompt might come from LangSmith and retrieval might call a remote
        # vector DB, so this pattern avoids unnecessary waiting.
        prompt_task = asyncio.create_task(load_prompt("customer_chat"))
        context_task = asyncio.create_task(retrieve_context(request.question, request.filters, request.top_k))

        # asyncio.gather waits until both tasks finish and returns their results
        # in the same order. If either task fails, the exception is caught below
        # and recorded in the audit log.
        system_prompt, chunks = await asyncio.gather(prompt_task, context_task)

        # The LLM receives only the system prompt, the user question, customer
        # metadata, and the retrieved chunks. This keeps answer generation
        # grounded in RentOut policy content.
        answer = await generate_answer(system_prompt=system_prompt, request=request, chunks=chunks)

        # Citations are built from retrieval metadata, not from the LLM output.
        # This prevents the model from inventing source names.
        citations = [
            Citation(
                document=chunk.document_title,
                section=chunk.section,
                version=chunk.version,
                source_path=chunk.source_path,
                score=chunk.score,
            )
            for chunk in chunks
        ]
        response = ChatResponse(
            conversation_id=conversation_id,
            answer=answer,
            citations=citations,
            metadata={
                "retrieved_chunks": len(chunks),
                "async_pattern": "prompt loading and context retrieval run concurrently",
            },
        )

        latency_ms = int((time.perf_counter() - started) * 1000)
        await write_audit_event(
            AuditEvent(
                conversation_id=conversation_id,
                question=request.question,
                status="success",
                latency_ms=latency_ms,
                retrieved_documents=[chunk.document_title for chunk in chunks],
            )
        )
        return response
    except Exception as exc:
        # Even failed requests are useful operational data. In production this
        # same event could be pushed to a logging platform or SIEM instead of a
        # local JSONL file.
        latency_ms = int((time.perf_counter() - started) * 1000)
        await write_audit_event(
            AuditEvent(
                conversation_id=conversation_id,
                question=request.question,
                status="error",
                latency_ms=latency_ms,
                error=str(exc),
            )
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ingest", response_model=IngestResponse)
async def ingest() -> IngestResponse:
    """Build the local vector store from the RentOut DOCX policy corpus."""
    return await ingest_documents()