import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag.schemas import RetrievedChunk


def test_chat_contract_with_mocked_rag(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_load_prompt(prompt_name: str) -> str:
        return "Answer from context only."

    async def fake_retrieve_context(question, filters=None, top_k=None):
        return [
            RetrievedChunk(
                chunk_id="c1",
                text="Customers may cancel before delivery if the route has not been loaded.",
                document_title="Cancellation and Early Return Policy",
                section="Pre-Delivery Cancellation",
                document_type="policy",
                department="support",
                audience="customer",
                version="v1.0",
                source_path="app/data/source_docs/cancellation.docx",
                score=0.91,
            )
        ]

    async def fake_generate_answer(system_prompt, request, chunks):
        return "You may cancel before delivery if the route has not been loaded."

    async def fake_write_audit_event(event):
        return None

    monkeypatch.setattr("app.api.routes_chat.load_prompt", fake_load_prompt)
    monkeypatch.setattr("app.api.routes_chat.retrieve_context", fake_retrieve_context)
    monkeypatch.setattr("app.api.routes_chat.generate_answer", fake_generate_answer)
    monkeypatch.setattr("app.api.routes_chat.write_audit_event", fake_write_audit_event)

    client = TestClient(app)
    response = client.post("/chat", json={"question": "Can I cancel before delivery?"})

    assert response.status_code == 200
    payload = response.json()
    assert "cancel before delivery" in payload["answer"]
    assert payload["citations"][0]["document"] == "Cancellation and Early Return Policy"
    assert payload["metadata"]["retrieved_chunks"] == 1

