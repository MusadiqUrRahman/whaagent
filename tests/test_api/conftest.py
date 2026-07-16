"""Test fixtures for API tests."""

import pytest

from whaagent.api.pool import TenantAgentPool


@pytest.fixture
def app_with_agent_pool():
    """Create an app with agent pool initialized for testing."""
    from whaagent.api.server import create_app

    app = create_app()
    # Initialize agent pool (normally done in lifespan)
    app.state.agent_pool = TenantAgentPool(max_size=10)
    return app
