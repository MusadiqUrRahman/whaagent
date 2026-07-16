"""Tests for API health endpoints."""

from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_returns_ok(self) -> None:
        """Health endpoint should return OK status."""
        from whaagent.api.server import create_app

        app = create_app()
        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_ready_returns_ok(self) -> None:
        """Ready endpoint should return ready status."""
        from whaagent.api.server import create_app

        app = create_app()
        client = TestClient(app)
        response = client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
