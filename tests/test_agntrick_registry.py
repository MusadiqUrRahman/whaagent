"""Tests for whaagent package - registry module."""

from whaagent.interfaces.base import Agent
from whaagent.registry import AgentRegistry


class MockAgent(Agent):
    """Mock agent for testing."""

    async def run(self, input_data, config=None):
        return "test response"

    def get_tools(self):
        return []


def test_whaagent_registry_register_and_get():
    """Test registering and retrieving an agent."""
    # Clean up first
    AgentRegistry._registry.pop("test-whaagent-agent", None)
    AgentRegistry._mcp_servers.pop("test-whaagent-agent", None)

    @AgentRegistry.register("test-whaagent-agent", mcp_servers=["fetch"])
    class TestAgent(MockAgent):
        pass

    try:
        # Verify registration
        assert AgentRegistry.get("test-whaagent-agent") is TestAgent
        assert "test-whaagent-agent" in AgentRegistry.list_agents()
        assert AgentRegistry.get_mcp_servers("test-whaagent-agent") == ["fetch"]
    finally:
        AgentRegistry._registry.pop("test-whaagent-agent", None)
        AgentRegistry._mcp_servers.pop("test-whaagent-agent", None)


def test_whaagent_registry_get_nonexistent():
    """Test getting a non-existent agent."""
    assert AgentRegistry.get("nonexistent-agent-xyz") is None


def test_whaagent_registry_list_agents():
    """Test listing all registered agents."""
    # Clean up first
    for name in ["list-test-1", "list-test-2"]:
        AgentRegistry._registry.pop(name, None)
        AgentRegistry._mcp_servers.pop(name, None)

    @AgentRegistry.register("list-test-1", mcp_servers=None)
    class ListTest1(MockAgent):
        pass

    @AgentRegistry.register("list-test-2", mcp_servers=["fetch"])
    class ListTest2(MockAgent):
        pass

    try:
        agents = AgentRegistry.list_agents()
        assert "list-test-1" in agents
        assert "list-test-2" in agents
    finally:
        for name in ["list-test-1", "list-test-2"]:
            AgentRegistry._registry.pop(name, None)
            AgentRegistry._mcp_servers.pop(name, None)


def test_whaagent_registry_discovers_bundled_agents():
    """Test that discover_agents finds bundled agents."""
    # Discover agents
    AgentRegistry.discover_agents()

    agents = AgentRegistry.list_agents()

    # Check for bundled agents
    assert "developer" in agents
    assert "github-pr-reviewer" in agents
    assert "learning" in agents
    assert "news" in agents
    assert "youtube" in agents
