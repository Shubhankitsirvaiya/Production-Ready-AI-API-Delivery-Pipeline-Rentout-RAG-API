"""Answer generation layer for the RentOut chatbot."""

# Keep annotations future-compatible.
from __future__ import annotations

# AsyncOpenAI allows the model call to be awaited without blocking FastAPI.
from openai import AsyncOpenAI

# Settings provide the API key and chat model name.
from app.core.config import get_settings

# ChatRequest contains user input; RetrievedChunk contains grounding evidence.
from app.rag.schemas import ChatRequest, RetrievedChunk


async def generate_answer(system_prompt: str, request: ChatRequest, chunks: list[RetrievedChunk]) -> str:
    """Generate a grounded answer from retrieved chunks."""

    # Read runtime configuration.
    settings = get_settings()

    # If no API key is configured, return a deterministic local demo response.
    if not settings.openai_api_key:
        return _fallback_answer(request, chunks)

    # Create an async OpenAI client for the network call.
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Convert structured chunks into prompt-ready text.
    context = _format_context(chunks)

    # Await the OpenAI chat completion call.
    response = await client.chat.completions.create(
        # Use the configured chat model.
        model=settings.openai_chat_model,
        # Send system instructions plus one user message containing context.
        messages=[
            # System prompt controls assistant behavior and grounding rules.
            {"role": "system", "content": system_prompt},
            # User message contains customer type, question, and retrieved context.
            {
                "role": "user",
                "content": (
                    # Include customer type so the model can adapt wording.
                    f"Customer type: {request.customer_type}\n"
                    # Include the actual question.
                    f"Question: {request.question}\n\n"
                    # Include retrieved policy chunks as grounding context.
                    f"Retrieved context:\n{context}"
                ),
            },
        ],
    )

    # Return model text, falling back to empty string if the SDK response is empty.
    return response.choices[0].message.content or ""


# Private helper that formats retrieved chunks for the LLM prompt.
def _format_context(chunks: list[RetrievedChunk]) -> str:
    """Turn structured retrieved chunks into a compact prompt section."""

    # Make the absence of context explicit inside the prompt.
    if not chunks:
        return "No retrieved context."

    # Join every chunk into a labeled source block.
    return "\n\n".join(
        (
            # Source header includes citation metadata and score.
            f"Source {index}: {chunk.document_title} | {chunk.section} | "
            # Keep score rounded for readability.
            f"{chunk.version} | score={chunk.score:.3f}\n{chunk.text}"
        )
        # Source numbers start at 1 for human readability.
        for index, chunk in enumerate(chunks, start=1)
    )


# Private helper used when no OpenAI key is present.
def _fallback_answer(request: ChatRequest, chunks: list[RetrievedChunk]) -> str:
    """Return a deterministic answer when OPENAI_API_KEY is not configured."""

    # If retrieval found nothing, explain the likely operational fix.
    if not chunks:
        return "No relevant RentOut policy context was found. Run ingestion or broaden your filters."

    # Summarize up to three retrieved sources in the local response.
    citations = ", ".join(f"{chunk.document_title} ({chunk.section})" for chunk in chunks[:3])

    # Return predictable text that tests and demos can use without paid API calls.
    return (
        # Echo the question so the response is tied to the request.
        f"Local fallback answer for: {request.question}\n\n"
        # Show the retrieved evidence titles.
        f"Relevant RentOut policy sources found: {citations}.\n"
        # Explain how to enable real generation.
        "Set OPENAI_API_KEY to enable full GPT answer generation."
    )