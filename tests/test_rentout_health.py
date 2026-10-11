# TestClient lets tests call FastAPI routes without starting Uvicorn.
from fastapi.testclient import TestClient

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