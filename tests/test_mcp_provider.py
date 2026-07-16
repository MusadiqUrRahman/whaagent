"""Tests for whaagent package - MCP provider module."""

from unittest.mock import MagicMock

import pytest

from whaagent.mcp.provider import MCPConnectionError, MCPProvider


class TestMCPConnectionError:
    """Test MCPConnectionError exception."""

    def test_mcp_connection_error_initialization(self):
        """Test MCPConnectionError initialization."""
        cause = Exception("connection failed")
        error = MCPConnectionError("test-server", cause)

        assert error.server_name == "test-server"
        assert error.cause == cause
        assert "Failed to connect to MCP server 'test-server'" in str(error)


class TestMCPProvider:
    """Test MCPProvider class."""

    def test_mcp_provider_initialization_with_servers_config(self):
        """Test MCPProvider initialization with servers config."""
        servers_config = {"test-server": MagicMock()}
        provider = MCPProvider(servers_config=servers_config)

        assert provider._config == servers_config

    def test_mcp_provider_client_property(self):
        """Test client property returns MultiServerMCPClient."""
        provider = MCPProvider(servers_config={"test": MagicMock()})

        assert provider.client is not None
        # Should be the same instance
        assert provider.client is provider.client

    def test_mcp_provider_initialization_with_server_names(self):
        """Test MCPProvider initialization with server names filter."""
        mock_servers_config = {
            "server1": MagicMock(),
            "server2": MagicMock(),
            "server3": MagicMock(),
        }

        provider = MCPProvider(servers_config=mock_servers_config, server_names=["server1", "server3"])

        assert "server1" in provider._config
        assert "server3" in provider._config
        assert "server2" not in provider._config

    def test_mcp_provider_unknown_server_raises_value_error(self):
        """Test MCPProvider raises ValueError for unknown server names."""
        servers_config = {"server1": MagicMock(), "server2": MagicMock()}

        with pytest.raises(ValueError, match="Unknown MCP server"):
            MCPProvider(servers_config=servers_config, server_names=["server1", "unknown_server"])

    def test_mcp_provider_all_known_servers_no_error(self):
        """Test MCPProvider accepts valid server names without error."""
        servers_config = {"server1": MagicMock(), "server2": MagicMock()}
        provider = MCPProvider(servers_config=servers_config, server_names=["server1"])
        assert "server1" in provider._config
        assert "server2" not in provider._config
