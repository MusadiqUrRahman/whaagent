"""Tests for WhatsApp QR code and status endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


class TestWhatsAppQREndpoints:
    """Tests for WhatsApp QR code endpoints."""

    def test_receive_qr_code_stores_it(self) -> None:
        """QR code POST endpoint should store the QR code."""
        from whaagent.api.server import create_app

        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/api/v1/whatsapp/qr/test-tenant",
            json={"image": "base64encodedimage"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "message" in data

    def test_receive_qr_code_invalid_payload(self) -> None:
        """QR code POST endpoint should reject invalid payload."""
        from whaagent.api.server import create_app

        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/api/v1/whatsapp/qr/test-tenant",
            json={},  # Missing image field
        )

        assert response.status_code == 422  # Validation error

    def test_qr_page_returns_html(self) -> None:
        """QR page endpoint should return HTML."""
        from whaagent.api.server import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/v1/whatsapp/qr/test-tenant/page")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        content = response.text
        assert "WhatsApp QR Code" in content
        assert "test-tenant" in content

    # Note: SSE testing (test_qr_stream_returns_sse) is better suited for integration tests
    # and is skipped here to avoid hanging unit tests


class TestWhatsAppStatusEndpoints:
    """Tests for WhatsApp status endpoints."""

    def test_receive_connected_status(self) -> None:
        """Status endpoint should store connected status."""
        from whaagent.api.server import create_app

        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/api/v1/whatsapp/status/test-tenant",
            json={"status": "connected", "phone": "+1234567890"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "message" in data

    def test_receive_disconnected_status(self) -> None:
        """Status endpoint should store disconnected status."""
        from whaagent.api.server import create_app

        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/api/v1/whatsapp/status/test-tenant",
            json={"status": "disconnected"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_receive_status_invalid_payload(self) -> None:
        """Status endpoint should reject invalid payload."""
        from whaagent.api.server import create_app

        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/api/v1/whatsapp/status/test-tenant",
            json={},  # Missing status field
        )

        assert response.status_code == 422  # Validation error

    def test_receive_connected_status_without_phone(self) -> None:
        """Status endpoint should accept connected status without phone."""
        from whaagent.api.server import create_app

        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/api/v1/whatsapp/status/test-tenant",
            json={"status": "connected"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestWhatsAppMCPInjection:
    """Tests that the WhatsApp webhook injects MCP tools into agents."""

    @patch("whaagent.api.routes.whatsapp.AgentRegistry")
    @patch("whaagent.api.routes.whatsapp.get_config")
    def test_webhook_injects_mcp_tools_into_agent(
        self,
        mock_config: MagicMock,
        mock_registry_cls: MagicMock,
    ) -> None:
        """WhatsApp webhook should pass mcp_server_names and tool_categories to agent."""
        from whaagent.api.pool import TenantAgentPool
        from whaagent.api.routes.whatsapp import get_whatsapp_registry
        from whaagent.api.server import create_app

        # Set up config mock with API key, LLM settings, and a tenant
        mock_tenant = MagicMock()
        mock_tenant.id = "test-tenant"
        mock_tenant.default_agent = "developer"
        mock_tenant.allowed_contacts = None  # Allow all contacts

        mock_config.return_value = MagicMock(
            auth=MagicMock(api_keys={"test-key": "test-tenant"}),
            llm=MagicMock(model="gpt-4", temperature=0.7),
            whatsapp=MagicMock(tenants=[mock_tenant]),
            storage=MagicMock(base_path=None),
        )

        # Set up WhatsApp registry mock via dependency override
        mock_registry_instance = MagicMock()
        mock_registry_instance.lookup_by_phone.return_value = "test-tenant"

        # Set up agent registry
        mock_registry_cls.discover_agents = MagicMock()

        # Create a mock agent instance that will be returned by the constructor
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(return_value="Hello from agent")

        # Create a mock agent class that tracks constructor kwargs
        mock_agent_cls = MagicMock()
        constructor_calls: list[dict[str, object]] = []

        def capture_constructor(**kwargs: object) -> MagicMock:
            constructor_calls.append(kwargs)
            return mock_agent_instance

        mock_agent_cls.side_effect = capture_constructor
        mock_registry_cls.get.return_value = mock_agent_cls
        mock_registry_cls.get_mcp_servers.return_value = ["toolbox"]
        mock_registry_cls.get_tool_categories.return_value = ["web", "hackernews"]

        app = create_app()
        # Initialize agent pool (normally done in lifespan)
        app.state.agent_pool = TenantAgentPool(max_size=10)
        app.dependency_overrides[get_whatsapp_registry] = lambda: mock_registry_instance
        client = TestClient(app)

        response = client.post(
            "/api/v1/channels/whatsapp/message",
            json={"from": "+1234567890", "message": "hello", "tenant_id": "test-tenant"},
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 200
        # Verify agent constructor received mcp_server_names and tool_categories
        assert len(constructor_calls) == 1
        args = constructor_calls[0]
        assert args.get("mcp_server_names") == ["toolbox"]
        assert args.get("tool_categories") == ["web", "hackernews"]


class TestWhatsAppMemoryPersistence:
    """Tests that the WhatsApp webhook uses persistent memory."""

    @patch("whaagent.api.routes.whatsapp.AgentRegistry")
    @patch("whaagent.api.routes.whatsapp.get_config")
    def test_webhook_passes_checkpointer_and_thread_id(
        self,
        mock_config: MagicMock,
        mock_registry_cls: MagicMock,
    ) -> None:
        """Webhook should pass a checkpointer and scoped thread_id to the agent."""
        from whaagent.api.pool import TenantAgentPool
        from whaagent.api.routes.whatsapp import get_whatsapp_registry
        from whaagent.api.server import create_app

        mock_tenant = MagicMock()
        mock_tenant.id = "tenant-1"
        mock_tenant.default_agent = "assistant"
        mock_tenant.allowed_contacts = None

        mock_config.return_value = MagicMock(
            auth=MagicMock(api_keys={"key": "val"}),
            llm=MagicMock(model="gpt-4", temperature=0.7),
            whatsapp=MagicMock(tenants=[mock_tenant]),
            storage=MagicMock(base_path=None),
        )

        mock_registry_instance = MagicMock()
        mock_registry_instance.lookup_by_phone.return_value = "tenant-1"

        mock_registry_cls.discover_agents = MagicMock()

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(return_value="Got it")

        mock_agent_cls = MagicMock()
        constructor_calls: list[dict[str, object]] = []

        def capture_constructor(**kwargs: object) -> MagicMock:
            constructor_calls.append(kwargs)
            return mock_agent_instance

        mock_agent_cls.side_effect = capture_constructor
        mock_registry_cls.get.return_value = mock_agent_cls
        mock_registry_cls.get_mcp_servers.return_value = []
        mock_registry_cls.get_tool_categories.return_value = ["web"]

        app = create_app()
        # Initialize agent pool (normally done in lifespan)
        app.state.agent_pool = TenantAgentPool(max_size=10)
        app.dependency_overrides[get_whatsapp_registry] = lambda: mock_registry_instance
        client = TestClient(app)

        response = client.post(
            "/api/v1/channels/whatsapp/message",
            json={"from": "+5511999999999", "message": "hello", "tenant_id": "tenant-1"},
            headers={"X-API-Key": "key"},
        )

        assert response.status_code == 200
        assert len(constructor_calls) == 1
        args = constructor_calls[0]

        # Verify thread_id is scoped per tenant + phone
        assert args["thread_id"] == "whatsapp:tenant-1:+5511999999999"

        # Verify checkpointer was created by the pool and passed to agent
        assert args.get("checkpointer") is not None
        # db_path was consumed by the pool to create the checkpointer
        assert args.get("db_path") is None  # Pool pops it
