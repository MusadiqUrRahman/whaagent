"""Tests for whaagent package - CLI module."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
import typer

from whaagent.cli import (
    _handle_mcp_connection_error,
    _print_chained_causes,
    _run_agent,
    agent_info,
    configure_logging,
    execute_agent,
    list_agents,
    show_config,
)
from whaagent.mcp import MCPConnectionError


class MockAgent:
    """Mock agent for CLI testing."""

    def __init__(self, initial_mcp_tools=None, _agent_name=None, tool_categories=None):
        self._initial_mcp_tools = initial_mcp_tools or []
        self._agent_name = _agent_name
        self._tool_categories = tool_categories

    async def run(self, input_data):
        return "mock response"

    def get_tools(self):
        return []

    @property
    def system_prompt(self):
        return "Mock system prompt"


def test_cli_configure_logging_verbose():
    """Test that verbose logging configures DEBUG level."""
    with patch("logging.basicConfig") as mock_basicConfig:
        configure_logging(verbose=True)
        mock_basicConfig.assert_called_once()
        call_kwargs = mock_basicConfig.call_args[1]
        assert call_kwargs["level"] == "DEBUG"


def test_cli_configure_logging_default():
    """Test that default logging configures INFO level."""
    with patch("logging.basicConfig") as mock_basicConfig:
        configure_logging(verbose=False)
        mock_basicConfig.assert_called_once()
        call_kwargs = mock_basicConfig.call_args[1]
        assert call_kwargs["level"] == "INFO"


def test_cli_print_chained_causes_no_cause():
    """Test _print_chained_causes with no cause."""
    error = Exception("root error")

    with patch("whaagent.cli.console") as mock_console:
        _print_chained_causes(error)
        mock_console.print.assert_not_called()


def test_cli_print_chained_causes_single_cause():
    """Test _print_chained_causes with one chained cause."""
    root = Exception("root error")
    cause1 = Exception("cause 1")
    root.__cause__ = cause1

    with patch("whaagent.cli.console") as mock_console:
        _print_chained_causes(root)
        mock_console.print.assert_called_once()


def test_cli_print_chained_causes_multiple_causes():
    """Test _print_chained_causes with multiple chained causes."""
    root = Exception("root error")
    cause1 = Exception("cause 1")
    cause2 = Exception("cause 2")
    root.__cause__ = cause1
    cause1.__cause__ = cause2

    with patch("whaagent.cli.console") as mock_console:
        _print_chained_causes(root)
        assert mock_console.print.call_count == 2


def test_cli_handle_mcp_connection_error_basic():
    """Test _handle_mcp_connection_error with basic error."""
    cause = Exception("connection failed")
    error = MCPConnectionError("test-server", cause)

    with patch("whaagent.cli.console") as mock_console:
        _handle_mcp_connection_error(error)
        assert mock_console.print.call_count >= 1


def test_cli_handle_mcp_connection_error_with_exceptions_attr():
    """Test _handle_mcp_connection_error when cause has exceptions attribute."""
    cause = MagicMock()
    cause.exceptions = [Exception("error1"), Exception("error2")]
    error = MCPConnectionError("fetch-server", cause)

    with patch("whaagent.cli.console") as mock_console:
        _handle_mcp_connection_error(error)
        assert mock_console.print.call_count >= 2


def test_cli_run_agent_without_mcp():
    """Test _run_agent without MCP tools."""
    agent_cls = MockAgent

    result = asyncio.run(_run_agent(agent_cls, "test input", None, "test-agent"))
    assert result == "mock response"


def test_cli_run_agent_with_mcp():
    """Test _run_agent with MCP tools."""
    agent_cls = MockAgent
    mock_mcp_tools = [MagicMock()]

    with patch("whaagent.cli.MCPProvider") as mock_provider_class:
        mock_provider = MagicMock()
        mock_provider.tool_session.return_value.__aenter__.return_value = mock_mcp_tools
        mock_provider_class.return_value = mock_provider

        result = asyncio.run(_run_agent(agent_cls, "test input", ["test-server"], "test-agent"))
        assert result == "mock response"
        mock_provider_class.assert_called_once_with(server_names=["test-server"])


def test_cli_execute_agent_missing_agent():
    """Test execute_agent with missing agent."""
    with patch("whaagent.cli.AgentRegistry.get") as mock_get:
        mock_get.return_value = None

        with pytest.raises(typer.Exit) as exc_info:
            execute_agent("nonexistent-agent", "test input", 60)
        assert exc_info.value.exit_code == 1


def test_cli_execute_agent_success():
    """Test execute_agent with successful execution."""
    with (
        patch("whaagent.cli.AgentRegistry.get") as mock_get,
        patch("whaagent.cli.AgentRegistry.get_mcp_servers") as mock_mcp,
        patch("asyncio.run") as mock_run,
    ):
        mock_get.return_value = MockAgent
        mock_mcp.return_value = None
        mock_run.return_value = "agent response"

        result = execute_agent("test-agent", "test input", 60)
        assert result == "agent response"


def test_cli_execute_agent_timeout():
    """Test execute_agent with timeout."""
    with (
        patch("whaagent.cli.AgentRegistry.get") as mock_get,
        patch("whaagent.cli.AgentRegistry.get_mcp_servers") as mock_mcp,
        patch("asyncio.run") as mock_run,
    ):
        mock_get.return_value = MockAgent
        mock_mcp.return_value = None
        mock_run.side_effect = asyncio.TimeoutError()

        with pytest.raises(TimeoutError) as exc_info:
            execute_agent("test-agent", "test input", 10)
        assert "timed out after 10s" in str(exc_info.value)


def test_cli_list_agents():
    """Test list_agents command."""
    with (
        patch("whaagent.cli.AgentRegistry.discover_agents") as mock_discover,
        patch("whaagent.cli.AgentRegistry.list_agents") as mock_list,
        patch("whaagent.cli.console") as mock_console,
    ):
        mock_list.return_value = ["agent1", "agent2"]

        list_agents()

        mock_discover.assert_called_once()
        mock_list.assert_called_once()
        mock_console.print.assert_called_once()


def test_cli_agent_info_missing():
    """Test agent_info with missing agent."""
    with patch("whaagent.cli.AgentRegistry.get") as mock_get, patch("whaagent.cli.console") as mock_console:
        mock_get.return_value = None

        with pytest.raises(typer.Exit) as exc_info:
            agent_info("nonexistent-agent")
            # Use mock_console to verify the error was printed
            assert mock_console.print.call_count >= 1
        assert exc_info.value.exit_code == 1


def test_cli_agent_info_success():
    """Test agent_info with valid agent."""
    with (
        patch("whaagent.cli.AgentRegistry.get") as mock_get,
        patch("whaagent.cli.AgentRegistry.get_mcp_servers") as mock_mcp,
        patch("whaagent.cli.console") as mock_console,
    ):
        mock_get.return_value = MockAgent
        mock_mcp.return_value = None

        agent_info("test-agent")

        assert mock_console.print.call_count >= 3  # Multiple print calls


def test_cli_show_config():
    """Test show_config displays configuration."""
    from whaagent.config import AgentsConfig, whaagentConfig, LLMConfig, LoggingConfig, MCPConfig

    # Create mock config with nested attributes
    mock_config = MagicMock(spec=whaagentConfig)
    mock_config.llm = MagicMock(spec=LLMConfig)
    mock_config.llm.provider = "test-provider"
    mock_config.llm.model = "test-model"
    mock_config.llm.temperature = 0.5
    mock_config.llm.max_tokens = None

    mock_config.logging = MagicMock(spec=LoggingConfig)
    mock_config.logging.level = "DEBUG"
    mock_config.logging.file = "/tmp/test.log"
    mock_config.logging.directory = "/tmp/logs"

    mock_config.mcp = MagicMock(spec=MCPConfig)
    mock_config.mcp.servers = {"fetch": {}}

    mock_config.agents = MagicMock(spec=AgentsConfig)
    mock_config.agents.prompts_dir = "/tmp/prompts"
    mock_config._config_path = "/tmp/config.yaml"

    with patch("whaagent.cli.get_config") as mock_get_config, patch("whaagent.cli.console") as mock_console:
        mock_get_config.return_value = mock_config

        show_config()

        assert mock_console.print.call_count >= 1
