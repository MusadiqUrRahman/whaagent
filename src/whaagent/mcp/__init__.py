"""MCP (Model Context Protocol) as an injectable resource for agents."""

from whaagent.mcp.config import DEFAULT_MCP_SERVERS, get_mcp_servers_config
from whaagent.mcp.interceptors import ResponseTruncator
from whaagent.mcp.provider import MCPConnectionError, MCPProvider

__all__ = [
    "DEFAULT_MCP_SERVERS",
    "get_mcp_servers_config",
    "MCPConnectionError",
    "MCPProvider",
    "ResponseTruncator",
]
