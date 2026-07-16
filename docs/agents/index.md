# Agents

Agents are the core building blocks of whaagent. Each agent is an AI assistant configured with specific capabilities.

## Agent Types

### Built-in Agents

whaagent comes with 5 bundled agents:

| Agent | Purpose | Tools |
|-------|---------|-------|
| [developer](built-in.md#developer) | Code exploration & editing | Codebase tools + MCP |
| [github-pr-reviewer](built-in.md#github-pr-reviewer) | PR review with inline comments | GitHub tools |
| [learning](built-in.md#learning) | Educational tutorials | MCP (fetch, web-forager) |
| [news](built-in.md#news) | News aggregation | MCP (fetch, web-forager) |
| [youtube](built-in.md#youtube) | Video transcript analysis | YouTube transcript tool |

### Custom Agents

Create your own agents by subclassing `AgentBase`:

```python
from whaagent import AgentBase, AgentRegistry

@AgentRegistry.register("my-agent", mcp_servers=["fetch"])
class MyAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You are a helpful assistant."
```

See [Custom Agents](custom.md) for detailed instructions.

## Agent Architecture

### Base Class

All agents inherit from `AgentBase` (alias for `LangGraphMCPAgent`):

```python
class AgentBase:
    def __init__(
        self,
        model_name: str | None = None,
        temperature: float | None = None,
        mcp_provider: MCPProvider | None = None,
        initial_mcp_tools: list | None = None,
        thread_id: str | None = None,
    ): ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Define the agent's behavior."""
        ...

    def local_tools(self) -> Sequence[Any]:
        """Return local Python tools."""
        return []

    async def run(self, input_data: str) -> str:
        """Execute the agent with input."""
        ...
```

### Tool Types

Agents can use two types of tools:

1. **Local Tools**: Python functions/classes defined in code
2. **MCP Tools**: Tools provided by MCP servers

### Registration

Register agents with the decorator:

```python
@AgentRegistry.register(
    "agent-name",
    mcp_servers=["fetch", "web-forager"],  # Optional MCP servers
)
class MyAgent(AgentBase):
    ...
```

## Running Agents

### CLI

```bash
whaagent developer -i "Explain this code"
```

### Python

```python
import asyncio
from whaagent import AgentRegistry
from whaagent.mcp import MCPProvider

async def run_agent():
    # Get the agent class
    agent_cls = AgentRegistry.get("developer")

    # With MCP tools
    mcp_servers = AgentRegistry.get_mcp_servers("developer")
    provider = MCPProvider(server_names=mcp_servers)

    async with provider.tool_session() as tools:
        agent = agent_cls(initial_mcp_tools=tools)
        result = await agent.run("Explain this codebase")
        return result

asyncio.run(run_agent())
```

## See Also

- [Built-in Agents](built-in.md) - Detailed agent documentation
- [Custom Agents](custom.md) - Create your own agents
- [Prompts](prompts.md) - Manage agent prompts
- [Tools](../tools/index.md) - Available tools
