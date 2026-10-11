from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_contract() -> None:
    client = TestClient(app)
    response = client.get("/version")
    assert response.status_code == 200
    payload = response.json()
    assert "app" in payload
    assert "version" in payload

