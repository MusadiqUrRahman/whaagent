# Getting Started

This guide will help you get up and running with whaagent in minutes.

## Prerequisites

- Python 3.12 or 3.13
- An LLM API key (Anthropic, OpenAI, or other supported provider)

## Installation

### Basic Installation

```bash
pip install whaagent
```

### With Optional Extras

```bash
# CLI tools (recommended for command-line usage)
pip install whaagent[cli]

# WhatsApp integration
pip install whaagent[whatsapp]

# Development dependencies
pip install whaagent[dev]

# Everything
pip install whaagent[all]
```

## Configuration

### 1. Set Your API Key

Choose your LLM provider and set the corresponding environment variable:

```bash
# Anthropic (recommended)
export ANTHROPIC_API_KEY=sk-ant-xxx

# OpenAI
export OPENAI_API_KEY=sk-xxx

# Google
export GOOGLE_API_KEY=xxx

# Other providers: MISTRAL_API_KEY, COHERE_API_KEY, etc.
```

### 2. (Optional) Create Config File

Create `.whaagent.yaml` in your project directory:

```yaml
# .whaagent.yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-6
  temperature: 0.7

logging:
  level: INFO
```

See [Configuration](configuration.md) for all options.

## Using the CLI

### List Available Agents

```bash
whaagent list
```

### Run an Agent

```bash
# Developer agent (code exploration)
whaagent developer -i "Explain the project structure"

# Learning agent (tutorials)
whaagent learning -i "Teach me about Python decorators"

# News agent
whaagent news -i "What are today's top tech stories?"

# YouTube agent
whaagent youtube -i "Summarize video dQw4w9WgXcQ"
```

### Get Agent Info

```bash
whaagent info developer
```

### Show Configuration

```bash
whaagent config
```

## Using as a Library

### Basic Agent

```python
import asyncio
from whaagent import AgentBase, AgentRegistry

# Register a custom agent
@AgentRegistry.register("hello")
class HelloAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You are a friendly greeting assistant."

# Run the agent
async def main():
    agent = HelloAgent()
    response = await agent.run("Say hello!")
    print(response)

asyncio.run(main())
```

### Agent with MCP Tools

```python
from whaagent import AgentBase, AgentRegistry
from whaagent.mcp import MCPProvider

@AgentRegistry.register("web-agent", mcp_servers=["fetch"])
class WebAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You can fetch and analyze web content."

async def main():
    provider = MCPProvider(server_names=["fetch"])
    async with provider.tool_session() as mcp_tools:
        agent = WebAgent(initial_mcp_tools=mcp_tools)
        response = await agent.run("Fetch and summarize https://example.com")
        print(response)

asyncio.run(main())
```

### Agent with Local Tools

```python
from typing import Sequence, Any
from whaagent import AgentBase, AgentRegistry
from whaagent.tools import CodeSearcher, FileFinderTool

@AgentRegistry.register("code-agent")
class CodeAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You are a code analysis assistant."

    def local_tools(self) -> Sequence[Any]:
        return [
            CodeSearcher("."),
            FileFinderTool("."),
        ]
```

## Next Steps

- [Configuration](configuration.md) - Full configuration options
- [Built-in Agents](agents/built-in.md) - Explore bundled agents
- [Custom Agents](agents/custom.md) - Create your own agents
- [Tools Overview](tools/index.md) - Available local tools
- [MCP Servers](mcp/index.md) - MCP integration guide
