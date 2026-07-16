"""Tests for the agents API route."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from whaagent.api.auth import verify_api_key
from whaagent.api.deps import get_database, get_tenant_manager
from whaagent.api.server import create_app
from whaagent.config import get_config


@pytest.fixture
def authed_client() -> TestClient:
    """Create a test client with a pre-configured API key and mocked deps."""
    config = get_config(force_reload=True)
    config.auth.api_keys = {"test-api-key": "test-tenant"}
    app = create_app()

    # Override dependencies
    async def _mock_verify():
        return "test-tenant"

    mock_db = MagicMock()
    mock_db.get_checkpointer.return_value = MagicMock()

    mock_manager = MagicMock()
    mock_manager.get_database.return_value = mock_db

    app.dependency_overrides[verify_api_key] = _mock_verify
    app.dependency_overrides[get_tenant_manager] = lambda: mock_manager
    app.dependency_overrides[get_database] = lambda: mock_db

    return TestClient(app)


def test_get_agents_returns_list(authed_client: TestClient) -> None:
    """Test that GET /api/v1/agents returns list with valid API key."""
    response = authed_client.get("/api/v1/agents")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_get_agents_without_key_returns_401() -> None:
    """Test that GET /api/v1/agents returns 401 without API key."""
    config = get_config(force_reload=True)
    config.auth.api_keys = {"test-api-key": "test-tenant"}
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v1/agents")

    assert response.status_code == 401


def test_post_agent_run_returns_response(authed_client: TestClient, monkeypatch) -> None:
    """Test that POST runs agent and returns response."""

    class MockAgent:
        def __init__(self, **kwargs):
            pass

        async def run(self, input_text: str) -> str:
            return f"Mock response to: {input_text}"

    monkeypatch.setattr(
        "whaagent.registry.AgentRegistry.get",
        lambda name: MockAgent if name == "test-agent" else None,
    )
    monkeypatch.setattr(
        "whaagent.registry.AgentRegistry.discover_agents",
        lambda: None,
    )

    response = authed_client.post(
        "/api/v1/agents/test-agent/run",
        json={"input": "Hello, world!", "thread_id": "test-thread"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["output"] == "Mock response to: Hello, world!"
    assert data["agent"] == "test-agent"


def test_post_agent_run_without_thread_id(authed_client: TestClient, monkeypatch) -> None:
    """Test that POST works without thread_id."""

    class MockAgent:
        def __init__(self, **kwargs):
            pass

        async def run(self, input_text: str) -> str:
            return f"Mock response to: {input_text}"

    monkeypatch.setattr(
        "whaagent.registry.AgentRegistry.get",
        lambda name: MockAgent if name == "test-agent" else None,
    )
    monkeypatch.setattr(
        "whaagent.registry.AgentRegistry.discover_agents",
        lambda: None,
    )

    response = authed_client.post(
        "/api/v1/agents/test-agent/run",
        json={"input": "Hello, world!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["output"] == "Mock response to: Hello, world!"


def test_post_nonexistent_agent_returns_404(authed_client: TestClient, monkeypatch) -> None:
    """Test that POST for nonexistent agent returns 404."""
    monkeypatch.setattr(
        "whaagent.registry.AgentRegistry.get",
        lambda name: None,
    )
    monkeypatch.setattr(
        "whaagent.registry.AgentRegistry.discover_agents",
        lambda: None,
    )

    response = authed_client.post(
        "/api/v1/agents/nonexistent/run",
        json={"input": "Hello, world!"},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_post_agent_run_without_key_returns_401() -> None:
    """Test that POST returns 401 without API key."""
    config = get_config(force_reload=True)
    config.auth.api_keys = {"test-api-key": "test-tenant"}
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/v1/agents/test-agent/run",
        json={"input": "Hello, world!"},
    )

    assert response.status_code == 401
