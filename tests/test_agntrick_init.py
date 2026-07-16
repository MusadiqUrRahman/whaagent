"""Tests for whaagent package - __init__ module (public API)."""

from whaagent import (
    AgentBase,
    AgentNotFoundError,
    AgentRegistry,
    whaagentConfig,
    ConfigurationError,
    PromptNotFoundError,
    __version__,
    detect_provider,
    get_config,
    get_default_model,
)


def test_whaagent_version():
    """Test package version."""
    # Version is read from pyproject.toml via importlib.metadata
    # Python normalizes "1.0.0-beta" to "1.0.0b0"
    assert __version__ == "1.0.0b0"


def test_whaagent_imports():
    """Test that all public API exports are available."""
    # Core classes
    assert AgentBase is not None
    assert AgentRegistry is not None

    # Configuration
    assert whaagentConfig is not None
    assert get_config is not None

    # LLM
    assert detect_provider is not None
    assert get_default_model is not None

    # Exceptions
    assert AgentNotFoundError is not None
    assert ConfigurationError is not None
    assert PromptNotFoundError is not None


def test_whaagent_agent_registry_available():
    """Test that AgentRegistry is functional from top-level import."""
    # Clean up first
    AgentRegistry._registry.pop("api-test-agent", None)
    AgentRegistry._mcp_servers.pop("api-test-agent", None)

    from whaagent.interfaces.base import Agent

    class TestAgent(Agent):
        async def run(self, input_data, config=None):
            return "test"

        def get_tools(self):
            return []

    @AgentRegistry.register("api-test-agent", mcp_servers=["fetch"])
    class APIAgent(TestAgent):
        pass

    try:
        assert AgentRegistry.get("api-test-agent") is APIAgent
        assert "api-test-agent" in AgentRegistry.list_agents()
    finally:
        AgentRegistry._registry.pop("api-test-agent", None)
        AgentRegistry._mcp_servers.pop("api-test-agent", None)


def test_whaagent_config_available():
    """Test that config functions work from top-level import."""
    config = get_config()
    assert config is not None
    assert isinstance(config, whaagentConfig)
