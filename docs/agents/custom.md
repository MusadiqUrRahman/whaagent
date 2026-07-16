# Creating Custom Agents

Learn how to create your own agents with custom behavior and tools.

## Basic Agent

The simplest agent just defines a system prompt:

```python
from whaagent import AgentBase, AgentRegistry

@AgentRegistry.register("greeting")
class GreetingAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You are a friendly greeting assistant. Always respond cheerfully."
```

Run it:
```bash
whaagent greeting -i "Hello there!"
```

## Agent with Local Tools

Add Python-based tools for custom functionality:

```python
from typing import Sequence, Any
from langchain_core.tools import StructuredTool
from whaagent import AgentBase, AgentRegistry

def get_weather(location: str) -> str:
    """Get current weather for a location."""
    # Your weather API logic here
    return f"Weather in {location}: Sunny, 72°F"

@AgentRegistry.register("weather")
class WeatherAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You are a weather assistant. Help users check weather conditions."

    def local_tools(self) -> Sequence[Any]:
        return [
            StructuredTool.from_function(
                func=get_weather,
                name="get_weather",
                description="Get current weather for a location",
            )
        ]
```

## Agent with MCP Servers

Connect to MCP servers for external capabilities:

```python
from whaagent import AgentBase, AgentRegistry

@AgentRegistry.register("web-researcher", mcp_servers=["fetch", "web-forager"])
class WebResearcherAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return """You are a research assistant.
        Use web search to find information and fetch content from URLs."""
```

## Agent with Both Tool Types

Combine local and MCP tools:

```python
from typing import Sequence, Any
from langchain_core.tools import StructuredTool
from whaagent import AgentBase, AgentRegistry
from whaagent.tools import CodeSearcher

def analyze_sentiment(text: str) -> str:
    """Analyze sentiment of text."""
    # Your sentiment analysis logic
    return "Positive sentiment detected"

@AgentRegistry.register("code-sentiment", mcp_servers=["fetch"])
class CodeSentimentAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "Analyze code and comments for sentiment and tone."

    def local_tools(self) -> Sequence[Any]:
        return [
            CodeSearcher("."),
            StructuredTool.from_function(
                func=analyze_sentiment,
                name="analyze_sentiment",
                description="Analyze sentiment of text",
            ),
        ]
```

## External Prompt Files

Load prompts from files for easier editing:

```python
from whaagent import AgentBase, AgentRegistry, load_prompt

@AgentRegistry.register("custom")
class CustomAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        # Tries: config override -> prompts/custom.md -> bundled -> fallback
        prompt = load_prompt("custom")
        if prompt:
            return prompt
        return "Default fallback prompt"
```

Create `./prompts/custom.md`:
```markdown
You are a specialized assistant for [domain].

## Capabilities
- [capability 1]
- [capability 2]

## Guidelines
- [guideline 1]
- [guideline 2]
```

## Configuration-Based Agent

Create agents dynamically from configuration:

```python
from pathlib import Path
from whaagent import AgentBase, AgentRegistry

def create_agent_from_config(name: str, prompt_path: str, mcp_servers: list[str]):
    """Create an agent from configuration."""

    prompt = Path(prompt_path).read_text()

    @AgentRegistry.register(name, mcp_servers=mcp_servers)
    class DynamicAgent(AgentBase):
        @property
        def system_prompt(self) -> str:
            return prompt

    return DynamicAgent

# Usage
create_agent_from_config(
    name="support",
    prompt_path="./prompts/support.md",
    mcp_servers=["fetch"],
)
```

## Multi-Agent Patterns

### Coordinator Pattern

One agent orchestrates others:

```python
from whaagent import AgentBase, AgentRegistry

@AgentRegistry.register("coordinator")
class CoordinatorAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return """You coordinate between specialized agents.
        Delegate tasks to the appropriate specialist:
        - developer: for code tasks
        - news: for news queries
        - learning: for tutorials"""

    async def run(self, input_data: str) -> str:
        # Custom orchestration logic
        # Can call other agents programmatically
        ...
```

### Router Pattern

Route requests to different agents:

```python
from whaagent import AgentBase, AgentRegistry

@AgentRegistry.register("router")
class RouterAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "Classify the request and route to the appropriate agent."

    def local_tools(self):
        return [
            # Tools to call other agents
        ]
```

## Advanced Configuration

### Custom Model Settings

```python
@AgentRegistry.register("creative")
class CreativeAgent(AgentBase):
    def __init__(self, **kwargs):
        super().__init__(
            model_name="claude-sonnet-4-6",
            temperature=0.9,  # Higher creativity
            **kwargs
        )

    @property
    def system_prompt(self) -> str:
        return "You are a creative writing assistant."
```

### Thread Management

For conversations with memory:

```python
@AgentRegistry.register("conversational")
class ConversationalAgent(AgentBase):
    def __init__(self, thread_id: str = "default", **kwargs):
        super().__init__(thread_id=thread_id, **kwargs)

    @property
    def system_prompt(self) -> str:
        return "You are a helpful conversational assistant."
```

## Best Practices

1. **Single Responsibility**: Each agent should focus on one domain
2. **Clear Prompts**: Be specific about capabilities and limitations
3. **Tool Documentation**: Document what each tool does
4. **Error Handling**: Tools should return error strings, not raise exceptions
5. **Test Coverage**: Write tests for custom tools and agent behavior

## See Also

- [Built-in Agents](built-in.md) - Reference implementations
- [Prompts](prompts.md) - Prompt management
- [Tools](../tools/index.md) - Available tools
- [Examples](../examples/) - More examples
