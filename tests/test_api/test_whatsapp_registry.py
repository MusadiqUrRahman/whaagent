"""Tests for WhatsApp registry functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from whaagent.api.deps import get_database, get_tenant_manager
from whaagent.api.server import create_app
from whaagent.config import WhatsAppTenantConfig, get_config
from whaagent.whatsapp import WhatsAppRegistry


@pytest.fixture
def mock_tenant_configs():
    """Mock tenant configurations for testing."""
    return [
        WhatsAppTenantConfig(
            id="personal",
            phone="+34611111111",
            default_agent="developer",
            allowed_contacts=["+34611111111", "+34622222222"],
            system_prompt="Personal assistant",
        ),
        WhatsAppTenantConfig(
            id="work",
            phone="+34633333333",
            default_agent="chef",
            allowed_contacts=["+34633333333"],
            system_prompt="Chef assistant",
        ),
    ]


class TestWhatsAppRegistry:
    """Test the WhatsApp registry functionality."""

    def test_registry_initialization(self, mock_tenant_configs):
        """Test registry initialization from tenant configs."""
        registry = WhatsAppRegistry(mock_tenant_configs)

        assert registry.lookup_by_phone("+34611111111") == "personal"
        assert registry.lookup_by_phone("+34633333333") == "work"
        assert registry.lookup_by_tenant("personal") == "+34611111111"
        assert registry.lookup_by_tenant("work") == "+34633333333"
        assert len(registry.get_all_tenants()) == 2
        assert len(registry.get_all_phones()) == 2

    def test_register_new_mapping(self, mock_tenant_configs):
        """Test registering new phone-tenant mappings."""
        registry = WhatsAppRegistry(mock_tenant_configs)

        # Register new mapping
        registry.register("test", "+34644444444")

        assert registry.lookup_by_phone("+34644444444") == "test"
        assert registry.lookup_by_tenant("test") == "+34644444444"

    def test_lookup_nonexistent(self, mock_tenant_configs):
        """Test lookup of non-existent phone or tenant."""
        registry = WhatsAppRegistry(mock_tenant_configs)

        assert registry.lookup_by_phone("+34699999999") is None
        assert registry.lookup_by_tenant("nonexistent") is None

    def test_duplicate_registration(self, mock_tenant_configs):
        """Test handling of duplicate phone registrations."""
        registry = WhatsAppRegistry(mock_tenant_configs)

        # Re-register with same phone but different tenant
        registry.register("new_tenant", "+34611111111")

        # Should now map to new tenant
        assert registry.lookup_by_phone("+34611111111") == "new_tenant"
        assert registry.lookup_by_tenant("new_tenant") == "+34611111111"
        # Old tenant mapping should be gone
        assert registry.lookup_by_tenant("personal") is None

    def test_register_phone_tenant_cleanup(self, mock_tenant_configs):
        """Test that registering one mapping cleans up old ones."""
        registry = WhatsAppRegistry(mock_tenant_configs)

        # First verify initial state
        assert registry.lookup_by_phone("+34611111111") == "personal"
        assert registry.lookup_by_tenant("personal") == "+34611111111"

        # Register new mapping with same phone, different tenant
        registry.register("work_new", "+34611111111")

        assert registry.lookup_by_phone("+34611111111") == "work_new"
        assert registry.lookup_by_tenant("work_new") == "+34611111111"
        assert registry.lookup_by_tenant("personal") is None

    def test_register_with_existing_tenant(self, mock_tenant_configs):
        """Test registering a new phone with an existing tenant."""
        registry = WhatsAppRegistry(mock_tenant_configs)

        # Register new phone for existing tenant
        registry.register("personal", "+34655555555")

        assert registry.lookup_by_phone("+34655555555") == "personal"
        assert registry.lookup_by_tenant("personal") == "+34655555555"
        # Original phone should be gone
        assert registry.lookup_by_phone("+34611111111") is None

    def test_get_all_tenants(self, mock_tenant_configs):
        """Test getting all tenant IDs."""
        registry = WhatsAppRegistry(mock_tenant_configs)

        tenants = registry.get_all_tenants()
        assert "personal" in tenants
        assert "work" in tenants
        assert len(tenants) == 2

    def test_get_all_phones(self, mock_tenant_configs):
        """Test getting all phone numbers."""
        registry = WhatsAppRegistry(mock_tenant_configs)

        phones = registry.get_all_phones()
        assert "+34611111111" in phones
        assert "+34633333333" in phones
        assert len(phones) == 2

    @pytest.fixture
    def authed_client(self, mock_tenant_configs) -> TestClient:
        """Create a test client with a pre-configured API key and mocked deps."""
        from whaagent.api.pool import TenantAgentPool

        config = get_config(force_reload=True)

        # Clear existing and set new api_keys
        config.auth.api_keys.clear()
        config.auth.api_keys["test-api-key"] = "test-tenant"

        # Add WhatsApp tenant configs - convert fixture to actual list
        config.whatsapp.tenants = list(mock_tenant_configs)
        app = create_app()

        # Initialize agent pool (normally done in lifespan)
        app.state.agent_pool = TenantAgentPool(max_size=10)

        # Override dependencies - don't override verify_api_key since webhook doesn't use it
        mock_db = MagicMock()
        mock_db.get_checkpointer.return_value = MagicMock()

        mock_manager = MagicMock()
        mock_manager.get_database.return_value = mock_db

        # app.dependency_overrides[verify_api_key] = _mock_verify
        app.dependency_overrides[get_tenant_manager] = lambda: mock_manager
        app.dependency_overrides[get_database] = lambda: mock_db

        return TestClient(app)

    @pytest.fixture
    def mock_whatsapp_registry(self):
        """Mock WhatsApp registry for testing."""
        from whaagent.whatsapp import WhatsAppRegistry

        return WhatsAppRegistry(mock_tenant_configs)

    @pytest.mark.asyncio
    async def test_webhook_endpoint_processes_message_successfully(self, authed_client: TestClient, monkeypatch):
        """Test that POST /api/v1/channels/whatsapp/message processes a message and returns a response."""

        # Mock agent execution with async run
        mock_agent_response = "Mock agent response to your message"
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_agent_response)
        mock_agent._ensure_initialized = AsyncMock(return_value=None)

        mock_agent_class = MagicMock(return_value=mock_agent)

        # Patch AgentRegistry at the import location used by whatsapp.py
        monkeypatch.setattr(
            "whaagent.api.routes.whatsapp.AgentRegistry.discover_agents",
            lambda: None,
        )
        monkeypatch.setattr(
            "whaagent.api.routes.whatsapp.AgentRegistry.get",
            lambda name: mock_agent_class if name == "developer" else None,
        )
        monkeypatch.setattr(
            "whaagent.api.routes.whatsapp.AgentRegistry.get_mcp_servers",
            lambda name: [],
        )
        monkeypatch.setattr(
            "whaagent.api.routes.whatsapp.AgentRegistry.get_tool_categories",
            lambda name: [],
        )

        # Mock WhatsApp registry to return the correct tenant
        mock_registry = MagicMock()
        mock_registry.lookup_by_phone.return_value = "personal"

        # Mock config to return tenant configuration
        mock_tenant = MagicMock()
        mock_tenant.id = "personal"
        mock_tenant.phone = "+34611111111"
        mock_tenant.default_agent = "developer"
        mock_tenant.allowed_contacts = ["+34611111111"]
        mock_tenant.system_prompt = "Personal assistant"

        with patch("whaagent.api.routes.whatsapp._whatsapp_registry", mock_registry):
            with patch("whaagent.api.routes.whatsapp.get_config") as mock_get_config:
                mock_config = MagicMock()
                mock_config.auth.api_keys = {"test-api-key": "test-tenant"}
                mock_config.llm.model = "gpt-4o-mini"
                mock_config.llm.temperature = 0.7
                mock_config.whatsapp.tenants = [mock_tenant]
                mock_get_config.return_value = mock_config

                # Send webhook request
                webhook_data = {"from": "+34611111111", "message": "Hello, world!", "tenant_id": "personal"}

                response = authed_client.post(
                    "/api/v1/channels/whatsapp/message", headers={"X-API-Key": "test-api-key"}, json=webhook_data
                )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "tenant_id" in data
        assert data["tenant_id"] == "personal"

    def test_webhook_unknown_phone_returns_404(self, authed_client: TestClient):
        """Test that unknown phone number returns error."""
        mock_registry = MagicMock()
        mock_registry.lookup_by_phone.return_value = None

        with patch("whaagent.api.routes.whatsapp._whatsapp_registry", mock_registry):
            with patch("whaagent.api.routes.whatsapp.get_config") as mock_get_config:
                mock_config = MagicMock()
                mock_config.auth.api_keys = {"test-api-key": "test-tenant"}
                mock_get_config.return_value = mock_config

                response = authed_client.post(
                    "/api/v1/channels/whatsapp/message",
                    headers={"X-API-Key": "test-api-key"},
                    json={"from": "+34699999999", "message": "Hello"},
                )

        assert response.status_code == 404
