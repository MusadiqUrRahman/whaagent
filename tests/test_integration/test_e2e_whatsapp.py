"""End-to-end integration test for WhatsApp API pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from whaagent.api.deps import get_database, get_tenant_manager
from whaagent.api.server import create_app
from whaagent.config import WhatsAppTenantConfig, get_config


@pytest.fixture
def mock_tenant_configs():
    """Mock tenant configurations for testing."""
    return [
        WhatsAppTenantConfig(
            id="personal",
            phone="+34611111111",
            default_agent="developer",
            allowed_contacts=["+34611111111"],
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


@pytest.fixture
def authed_client(mock_tenant_configs) -> TestClient:
    """Create a test client with a pre-configured API key and mocked deps."""
    from whaagent.api.pool import TenantAgentPool

    config = get_config(force_reload=True)

    # Clear existing and set new api_keys
    config.auth.api_keys.clear()
    config.auth.api_keys["test-api-key"] = "personal"

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

    app.dependency_overrides[get_tenant_manager] = lambda: mock_manager
    app.dependency_overrides[get_database] = lambda: mock_db

    return TestClient(app)


@pytest.mark.asyncio
async def test_e2e_whatsapp_pipeline_success(authed_client: TestClient, monkeypatch):
    """Test the complete WhatsApp API pipeline from webhook to agent response."""

    # Mock agent execution with async run
    mock_agent_response = "Mock agent response: Hello! I'm your personal developer assistant."
    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_agent_response)
    mock_agent._ensure_initialized = AsyncMock(return_value=None)

    mock_agent_class = MagicMock(return_value=mock_agent)

    # Patch AgentRegistry
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
            mock_config.auth.api_keys = {"test-api-key": "personal"}
            mock_config.llm.model = "gpt-4o-mini"
            mock_config.llm.temperature = 0.7
            mock_config.whatsapp.tenants = [mock_tenant]
            mock_get_config.return_value = mock_config

            # Send webhook request
            webhook_data = {"from": "+34611111111", "message": "Hello, world!", "tenant_id": "personal"}

            response = authed_client.post(
                "/api/v1/channels/whatsapp/message", headers={"X-API-Key": "test-api-key"}, json=webhook_data
            )

    # Verify the response
    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "response" in data
    assert "tenant_id" in data
    assert data["tenant_id"] == "personal"
    assert data["response"] == mock_agent_response

    # Verify agent was called with the correct message and config
    mock_agent.run.assert_called_once_with(
        "Hello, world!", config={"configurable": {"thread_id": "whatsapp:personal:+34611111111"}}
    )


@pytest.mark.asyncio
async def test_e2e_whatsapp_pipeline_multiple_agents(authed_client: TestClient, monkeypatch):
    """Test the WhatsApp API pipeline with different agents."""

    # Mock two different agents
    dev_response = "Mock developer agent response: I'll help you with your coding questions."
    chef_response = "Mock chef agent response: Let's cook something delicious together!"

    mock_dev_agent = MagicMock()
    mock_dev_agent.run = AsyncMock(return_value=dev_response)
    mock_dev_agent._ensure_initialized = AsyncMock(return_value=None)
    mock_dev_agent_class = MagicMock(return_value=mock_dev_agent)

    mock_chef_agent = MagicMock()
    mock_chef_agent.run = AsyncMock(return_value=chef_response)
    mock_chef_agent._ensure_initialized = AsyncMock(return_value=None)
    mock_chef_agent_class = MagicMock(return_value=mock_chef_agent)

    # Patch AgentRegistry
    def mock_get_agent(name):
        if name == "developer":
            return mock_dev_agent_class
        elif name == "chef":
            return mock_chef_agent_class
        return None

    monkeypatch.setattr(
        "whaagent.api.routes.whatsapp.AgentRegistry.discover_agents",
        lambda: None,
    )
    monkeypatch.setattr(
        "whaagent.api.routes.whatsapp.AgentRegistry.get",
        mock_get_agent,
    )
    monkeypatch.setattr(
        "whaagent.api.routes.whatsapp.AgentRegistry.get_mcp_servers",
        lambda name: [],
    )
    monkeypatch.setattr(
        "whaagent.api.routes.whatsapp.AgentRegistry.get_tool_categories",
        lambda name: [],
    )

    # Mock WhatsApp registry
    mock_registry = MagicMock()
    mock_registry.lookup_by_phone.side_effect = lambda phone: {"+34611111111": "personal", "+34633333333": "work"}.get(
        phone
    )

    with patch("whaagent.api.routes.whatsapp._whatsapp_registry", mock_registry):
        with patch("whaagent.api.routes.whatsapp.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.auth.api_keys = {"test-api-key": "personal", "work-api-key": "work"}
            mock_config.llm.model = "gpt-4o-mini"
            mock_config.llm.temperature = 0.7

            # Create mock tenants
            personal_tenant = MagicMock()
            personal_tenant.id = "personal"
            personal_tenant.phone = "+34611111111"
            personal_tenant.default_agent = "developer"
            personal_tenant.allowed_contacts = ["+34611111111"]
            personal_tenant.system_prompt = "Personal assistant"

            work_tenant = MagicMock()
            work_tenant.id = "work"
            work_tenant.phone = "+34633333333"
            work_tenant.default_agent = "chef"
            work_tenant.allowed_contacts = ["+34633333333"]
            work_tenant.system_prompt = "Chef assistant"

            mock_config.whatsapp.tenants = [personal_tenant, work_tenant]
            mock_get_config.return_value = mock_config

            # Test personal tenant
            webhook_data_personal = {"from": "+34611111111", "message": "How do I Python?", "tenant_id": "personal"}

            response_personal = authed_client.post(
                "/api/v1/channels/whatsapp/message", headers={"X-API-Key": "test-api-key"}, json=webhook_data_personal
            )

            # Test work tenant
            webhook_data_work = {"from": "+34633333333", "message": "Recipe for pasta?", "tenant_id": "work"}

            response_work = authed_client.post(
                "/api/v1/channels/whatsapp/message", headers={"X-API-Key": "work-api-key"}, json=webhook_data_work
            )

    # Verify responses
    assert response_personal.status_code == 200
    data_personal = response_personal.json()
    assert data_personal["tenant_id"] == "personal"
    assert data_personal["response"] == dev_response
    mock_dev_agent.run.assert_called_once_with(
        "How do I Python?", config={"configurable": {"thread_id": "whatsapp:personal:+34611111111"}}
    )

    assert response_work.status_code == 200
    data_work = response_work.json()
    assert data_work["tenant_id"] == "work"
    assert data_work["response"] == chef_response
    mock_chef_agent.run.assert_called_once_with(
        "Recipe for pasta?", config={"configurable": {"thread_id": "whatsapp:work:+34633333333"}}
    )


@pytest.mark.asyncio
async def test_e2e_whatsapp_pipeline_unknown_phone_returns_404(authed_client: TestClient, monkeypatch):
    """Test that unknown phone number returns 404."""

    mock_registry = MagicMock()
    mock_registry.lookup_by_phone.return_value = None

    with patch("whaagent.api.routes.whatsapp._whatsapp_registry", mock_registry):
        with patch("whaagent.api.routes.whatsapp.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.auth.api_keys = {"test-api-key": "personal"}
            mock_get_config.return_value = mock_config

            response = authed_client.post(
                "/api/v1/channels/whatsapp/message",
                headers={"X-API-Key": "test-api-key"},
                json={"from": "+34699999999", "message": "Hello"},
            )

    assert response.status_code == 404
    assert "No tenant found for phone number" in response.json()["detail"]


@pytest.mark.asyncio
async def test_e2e_whatsapp_pipeline_invalid_phone_mapping_returns_400(authed_client: TestClient, monkeypatch):
    """Test that invalid phone-tenant mapping returns 400."""

    mock_registry = MagicMock()
    mock_registry.lookup_by_phone.return_value = "personal"  # Phone maps to personal

    with patch("whaagent.api.routes.whatsapp._whatsapp_registry", mock_registry):
        with patch("whaagent.api.routes.whatsapp.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.auth.api_keys = {"test-api-key": "personal"}
            mock_get_config.return_value = mock_config

            response = authed_client.post(
                "/api/v1/channels/whatsapp/message",
                headers={"X-API-Key": "test-api-key"},
                json={"from": "+34611111111", "message": "Hello", "tenant_id": "work"},  # Claims to be work
            )

    assert response.status_code == 400
    assert "does not match" in response.json()["detail"]


def test_e2e_whatsapp_pipeline_missing_auth_returns_401(authed_client: TestClient, monkeypatch):
    """Test that missing authentication returns 401."""

    mock_registry = MagicMock()
    mock_registry.lookup_by_phone.return_value = "personal"

    with patch("whaagent.api.routes.whatsapp._whatsapp_registry", mock_registry):
        response = authed_client.post(
            "/api/v1/channels/whatsapp/message",
            json={"from": "+34611111111", "message": "Hello"},
        )

    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_e2e_whatsapp_pipeline_missing_fields_returns_400(authed_client: TestClient, monkeypatch):
    """Test that missing required fields returns 400."""

    mock_registry = MagicMock()
    mock_registry.lookup_by_phone.return_value = "personal"

    with patch("whaagent.api.routes.whatsapp._whatsapp_registry", mock_registry):
        # Missing 'message' field
        response = authed_client.post(
            "/api/v1/channels/whatsapp/message",
            headers={"X-API-Key": "test-api-key"},
            json={"from": "+34611111111"},
        )

    assert response.status_code == 400
    assert "Missing 'from' or 'message'" in response.json()["detail"]


class TestSmarterAssistantIntegration:
    """Integration tests for the smarter WhatsApp assistant graph."""

    @pytest.mark.asyncio
    async def test_full_graph_flow_with_chat_intent(self) -> None:
        """Chat messages skip executor, go directly to responder."""
        from langchain_core.messages import AIMessage, HumanMessage

        from whaagent.graph import create_assistant_graph

        mock_model = AsyncMock()

        # Router returns chat intent
        router_response = AIMessage(content='{"intent": "chat", "tool_plan": null, "skip_tools": true}')
        # Responder returns formatted chat
        responder_response = AIMessage(content="Good morning! How can I help?")

        mock_model.ainvoke = AsyncMock(side_effect=[router_response, responder_response])

        graph = create_assistant_graph(
            model=mock_model,
            tools=[],
            system_prompt="You are helpful.",
        )

        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content="good morning")],
                "intent": "",
                "tool_plan": None,
                "progress": [],
                "final_response": None,
            },
            config={"configurable": {"thread_id": "test-chat"}},
        )

        assert result["final_response"] is not None
        assert result["intent"] == "chat"

    @pytest.mark.asyncio
    async def test_full_graph_flow_with_tool_use_intent(self) -> None:
        """Tool-use messages go through executor then responder."""
        from langchain_core.messages import AIMessage, HumanMessage

        from whaagent.graph import create_assistant_graph

        mock_model = AsyncMock()

        # Router returns tool_use intent
        router_response = AIMessage(
            content='{"intent": "tool_use", "tool_plan": "use web_search for weather", "skip_tools": false}'
        )
        # Sub-agent returns result
        sub_agent_response = AIMessage(content="Weather in São Paulo: 28°C, sunny")
        # Responder formats the result
        responder_response = AIMessage(content="São Paulo: 28°C, sunny ☀️")

        mock_model.ainvoke = AsyncMock(side_effect=[router_response, responder_response])

        graph = create_assistant_graph(
            model=mock_model,
            tools=[],
            system_prompt="You are helpful.",
        )

        with patch("whaagent.graph.create_agent") as mock_create_agent:
            mock_sub_graph = AsyncMock()
            mock_sub_graph.ainvoke = AsyncMock(return_value={"messages": [sub_agent_response]})
            mock_create_agent.return_value = mock_sub_graph

            result = await graph.ainvoke(
                {
                    "messages": [HumanMessage(content="What's the weather in São Paulo?")],
                    "intent": "",
                    "tool_plan": None,
                    "progress": [],
                    "final_response": None,
                },
                config={"configurable": {"thread_id": "test-tool"}},
            )

        assert result["intent"] == "tool_use"
        assert result["final_response"] is not None
