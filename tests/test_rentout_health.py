# TestClient lets tests call FastAPI routes without starting Uvicorn.
from fastapi.testclient import TestClient

# SimpleNamespace creates small fake settings objects for endpoint isolation.
from types import SimpleNamespace

# Import the actual FastAPI app object used in production.
from app.main import app


# Test the cheapest liveness endpoint.
def test_health_returns_ok() -> None:
    # Create a synchronous test client around the FastAPI app.
    client = TestClient(app)

    # Send a GET request to /health.
    response = client.get("/health")

    # The endpoint should respond successfully.
    assert response.status_code == 200

    # The JSON contract should stay stable for Docker/CI checks.
    assert response.json() == {"status": "ok"}


# Test the version endpoint contract.
def test_version_contract() -> None:
    # Create a test client for the app.
    client = TestClient(app)

    # Send a GET request to /version.
    response = client.get("/version")

    # The endpoint should respond successfully.
    assert response.status_code == 200

    # Parse the response body as JSON.
    payload = response.json()

    # Version response should include app name.
    assert "app" in payload

    # Version response should include version string.
    assert "version" in payload


# Verify Kubernetes readiness succeeds when a non-empty vector file exists.
def test_readiness_reports_vector_store(monkeypatch, tmp_path) -> None:
    # Create the smallest non-empty stand-in for an ingested vector store.
    vector_store = tmp_path / "vectors.json"
    vector_store.write_text("{}", encoding="utf-8")

    # Replace only the route's settings dependency with the temporary path.
    monkeypatch.setattr(
        "app.api.routes_health.get_settings",
        lambda: SimpleNamespace(vector_store_path=vector_store),
    )

    client = TestClient(app)
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "vector_store": True}


# Verify operational metadata is exposed without returning any secret value.
def test_operations_status_contract(monkeypatch) -> None:
    # Fake Kubernetes Downward API settings make the response deterministic.
    fake_settings = SimpleNamespace(
        deployment_environment="test",
        pod_name="rentout-api-example",
        pod_namespace="rentout-test",
        node_name="minikube",
        app_version="abc123def456",
        langsmith_tracing=False,
        langsmith_api_key=None,
        langsmith_project="rentout-project-12-test",
    )
    monkeypatch.setattr("app.api.routes_health.get_settings", lambda: fake_settings)

    client = TestClient(app)
    response = client.get("/ops/status")

    assert response.status_code == 200
    assert response.json()["environment"] == "test"
    assert response.json()["pod_name"] == "rentout-api-example"
    assert response.json()["langsmith_tracing"] is False
    # A secret key must never become part of this public status contract.
    assert "langsmith_api_key" not in response.json()
