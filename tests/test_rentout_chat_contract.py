# pytest provides monkeypatch and async test support.
import pytest

# TestClient lets us call FastAPI routes without starting a real server.
from fastapi.testclient import TestClient

# Import the real FastAPI app object.
from app.main import app

# RetrievedChunk is used to build fake retrieval results.
from app.rag.schemas import RetrievedChunk


# Test /chat without calling OpenAI or reading a real vector store.
def test_chat_contract_with_mocked_rag(monkeypatch: pytest.MonkeyPatch) -> None:
    # Fake prompt loader returns a simple system prompt.
    async def fake_load_prompt(prompt_name: str) -> str:
        # The route passes "customer_chat" here; the fake ignores exact value.
        return "Answer from context only."

    # Fake retriever returns one deterministic policy chunk.
    async def fake_retrieve_context(question, filters=None, top_k=None):
        # Return the same structure the real retriever would return.
        return [
            RetrievedChunk(
                # Stable fake chunk id.
                chunk_id="c1",
                # Fake source text.
                text="Customers may cancel before delivery if the route has not been loaded.",
                # Fake document title used in citations.
                document_title="Cancellation and Early Return Policy",
                # Fake section name.
                section="Pre-Delivery Cancellation",
                # Fake document type.
                document_type="policy",
                # Fake department.
                department="support",
                # Fake audience.
                audience="customer",
                # Fake version.
                version="v1.0",
                # Fake source path.
                source_path="app/data/source_docs/cancellation.docx",
                # Fake retrieval score.
                score=0.91,
            )
        ]

    # Fake answer generator avoids an OpenAI call during the test.
    async def fake_generate_answer(system_prompt, request, chunks):
        # Return predictable text that the assertion can check.
        return "You may cancel before delivery if the route has not been loaded."

    # Fake audit writer avoids touching local log files during this route test.
    async def fake_write_audit_event(event):
        # Do nothing; the route only needs this awaitable to succeed.
        return None

    # Replace the route module's prompt loader with our fake async function.
    monkeypatch.setattr("app.api.routes_chat.load_prompt", fake_load_prompt)

    # Replace the route module's retriever with our fake async function.
    monkeypatch.setattr("app.api.routes_chat.retrieve_context", fake_retrieve_context)

    # Replace the route module's answer generator with our fake async function.
    monkeypatch.setattr("app.api.routes_chat.generate_answer", fake_generate_answer)

    # Replace the route module's audit writer with our fake async function.
    monkeypatch.setattr("app.api.routes_chat.write_audit_event", fake_write_audit_event)

    # Create a test client around the FastAPI app.
    client = TestClient(app)

    # Send a POST /chat request matching ChatRequest.
    response = client.post("/chat", json={"question": "Can I cancel before delivery?"})

    # The route should succeed.
    assert response.status_code == 200

    # Parse response JSON into a dictionary.
    payload = response.json()

    # Answer should contain the fake response text.
    assert "cancel before delivery" in payload["answer"]

    # Citation should come from fake retrieval metadata.
    assert payload["citations"][0]["document"] == "Cancellation and Early Return Policy"

    # Metadata should report one retrieved chunk.
    assert payload["metadata"]["retrieved_chunks"] == 1