# Bundled MCP Servers

whaagent comes with two bundled MCP servers.

## fetch

Fetch content from specific URLs.

### Configuration

```yaml
mcp:
  servers:
    fetch:
      url: https://remote.mcpservers.org/fetch/mcp
      transport: http
```

### Capabilities
- Fetch HTML content from URLs
- Extract readable text from web pages
- Handle redirects and cookies

### Use Cases
- Reading documentation
- Fetching articles
- Accessing web APIs

### Example

```python
from whaagent import AgentBase, AgentRegistry

@AgentRegistry.register("fetcher", mcp_servers=["fetch"])
class FetcherAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You can fetch and analyze web content."

# Usage
agent = FetcherAgent(initial_mcp_tools=mcp_tools)
result = await agent.run("Fetch and summarize https://docs.python.org/3/library/asyncio.html")
```

---

## web-forager

Web search capabilities.

### Configuration

```yaml
mcp:
  servers:
    web-forager:
      command: uvx
      args: ["web-forager"]
      transport: stdio
```

### Requirements
- Requires `uvx` to be installed
- Internet connection

### Capabilities
- Web search
- Result aggregation
- Content extraction

### Use Cases
- Research tasks
- Finding information
- Comparing sources

### Example

```python
from whaagent import AgentBase, AgentRegistry

@AgentRegistry.register("researcher", mcp_servers=["web-forager"])
class ResearcherAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You can search the web for information."

# Usage
agent = ResearcherAgent(initial_mcp_tools=mcp_tools)
result = await agent.run("What are the latest developments in quantum computing?")
```

---

## Combined Usage

Use both servers together for comprehensive web capabilities:

```python
@AgentRegistry.register(
    "web-master",
    mcp_servers=["fetch", "web-forager"]
)
class WebMasterAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return """You can search the web and fetch content.
        First search for relevant information, then fetch detailed content from promising URLs."""
```

---

## Troubleshooting

### fetch Connection Errors

```
Error: Failed to connect to fetch server
```

**Solutions:**
1. Check internet connection
2. Verify the URL is accessible
3. Check for proxy/firewall issues

### web-forager Not Found

```
Error: uvx: command not found
```

**Solutions:**
1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Verify uvx is in PATH

### Timeout Issues

```
Error: Connection timed out
```

**Solutions:**
1. Increase timeout in config:
   ```yaml
   mcp:
     connection_timeout: 30
   ```
2. Check network stability

---

## Custom Servers

Add your own MCP servers:

```yaml
mcp:
  custom:
    my-server:
      url: https://my-server.com/mcp
      transport: sse
```

Or programmatically:

```python
from whaagent.mcp.config import register_mcp_server

register_mcp_server(
    "my-server",
    url="https://my-server.com/mcp",
    transport="sse",
)
```

## See Also

- [MCP Overview](index.md) - MCP integration
- [Configuration](../configuration.md) - Full configuration
- [Custom Agents](../agents/custom.md) - Using MCP in agents
