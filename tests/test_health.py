from fastapi.testclient import TestClient

from app.main import app


def test_root_endpoint():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200

    body = response.json()

    assert body["message"] == (
        "Parser Management System"
    )

    assert body["documentation"] == (
        "/docs"
    )


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "healthy"

    assert body["application"] == (
        "Parser Management System"
    )

    assert body["version"] == "0.1.0"


def test_readiness_endpoint():
    with TestClient(app) as client:
        response = client.get(
            "/health/ready"
        )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "ready"
    assert body["checks"]["api"] is True

    assert (
        body["checks"]["database"]
        is True
    )
