# MCP (Model Context Protocol)

MCP enables agents to use external tools through standardized servers.

## What is MCP?

Model Context Protocol (MCP) is a standardized way for AI agents to interact with external tools and services. whaagent supports MCP servers for extended capabilities.

## Bundled Servers

| Server | Purpose |
|--------|---------|
| [fetch](servers.md#fetch) | Fetch content from URLs |
| [web-forager](servers.md#web-forager) | Web search capabilities |

## Using MCP in Agents

### Registration

Specify MCP servers when registering an agent:

```python
from whaagent import AgentBase, AgentRegistry

@AgentRegistry.register("web-agent", mcp_servers=["fetch", "web-forager"])
class WebAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You can fetch web content and search the web."
```

### Running with MCP

```python
from whaagent import AgentRegistry
from whaagent.mcp import MCPProvider

agent_cls = AgentRegistry.get("web-agent")
mcp_servers = AgentRegistry.get_mcp_servers("web-agent")

provider = MCPProvider(server_names=mcp_servers)
async with provider.tool_session() as mcp_tools:
    agent = agent_cls(initial_mcp_tools=mcp_tools)
    result = await agent.run("Search for Python tutorials")
```

## MCP Provider

### Connection Management

```python
from whaagent.mcp import MCPProvider

# Create provider with specific servers
provider = MCPProvider(
    server_names=["fetch", "web-forager"],
    connection_timeout=15,  # seconds
)

# Use as context manager
async with provider.tool_session() as tools:
    print(f"Connected tools: {[t.name for t in tools]}")
```

### Error Handling

```python
from whaagent.mcp import MCPConnectionError

try:
    async with provider.tool_session() as tools:
        # Use tools
        pass
except MCPConnectionError as e:
    print(f"Failed to connect: {e}")
    print(f"Server: {e.server_name}")
```

## Configuration

### In YAML

```yaml
# .whaagent.yaml
mcp:
  connection_timeout: 15
  fail_fast: true

  servers:
    fetch:
      url: https://remote.mcpservers.org/fetch/mcp
      transport: http

    web-forager:
      command: uvx
      args: ["web-forager"]
      transport: stdio

  custom:
    my-server:
      url: https://my-server.com/mcp
      transport: sse
```

### Transport Types

| Transport | Description |
|-----------|-------------|
| `http` | HTTP-based MCP server |
| `stdio` | Local command with stdio communication |
| `sse` | Server-Sent Events |

## Custom MCP Servers

### Registering Custom Servers

```python
from whaagent.mcp.config import register_mcp_server

register_mcp_server(
    "my-custom-server",
    url="https://my-server.com/mcp",
    transport="sse",
)
```

### Using Custom Servers

```python
@AgentRegistry.register("custom", mcp_servers=["my-custom-server"])
class CustomAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You use custom tools."
```

## See Also

- [MCP Servers](servers.md) - Bundled server details
- [Configuration](../configuration.md) - MCP configuration
- [Custom Agents](../agents/custom.md) - Using MCP in agents
