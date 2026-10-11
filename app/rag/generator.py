"""Answer generation layer for the RentOut chatbot.

The generator is deliberately separate from retrieval. Retrieval decides what
context is relevant; generation decides how to explain that context to the user.
This separation makes the system easier to test and easier to improve later.
"""

from __future__ import annotations

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.rag.schemas import ChatRequest, RetrievedChunk


async def generate_answer(system_prompt: str, request: ChatRequest, chunks: list[RetrievedChunk]) -> str:
    """Generate a grounded answer from retrieved chunks.

    Arguments:
    - system_prompt: Behavior instructions loaded from the prompt registry.
    - request: Validated user input from FastAPI/Pydantic.
    - chunks: Top retrieved policy chunks selected by the retriever.

    The function is async because OpenAI calls are network I/O. While this call
    waits for the model response, the server can continue handling other work.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        return _fallback_answer(request, chunks)

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    context = _format_context(chunks)
    response = await client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Customer type: {request.customer_type}\n"
                    f"Question: {request.question}\n\n"
                    f"Retrieved context:\n{context}"
                ),
            },
        ],
    )
    return response.choices[0].message.content or ""


def _format_context(chunks: list[RetrievedChunk]) -> str:
    """Turn structured retrieved chunks into a compact prompt section."""
    if not chunks:
        return "No retrieved context."
    return "\n\n".join(
        (
            f"Source {index}: {chunk.document_title} | {chunk.section} | "
            f"{chunk.version} | score={chunk.score:.3f}\n{chunk.text}"
        )
        for index, chunk in enumerate(chunks, start=1)
    )


def _fallback_answer(request: ChatRequest, chunks: list[RetrievedChunk]) -> str:
    """Return a deterministic answer when OPENAI_API_KEY is not configured.

    This keeps demos, CI tests, and Docker startup checks useful even when no
    paid API key is available. Real answer generation is enabled by setting the
    key in `.env`.
    """
    if not chunks:
        return "No relevant RentOut policy context was found. Run ingestion or broaden your filters."
    citations = ", ".join(f"{chunk.document_title} ({chunk.section})" for chunk in chunks[:3])
    return (
        f"Local fallback answer for: {request.question}\n\n"
        f"Relevant RentOut policy sources found: {citations}.\n"
        "Set OPENAI_API_KEY to enable full GPT answer generation."
    )