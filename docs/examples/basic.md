# Basic Agent Example

The simplest way to create an agent.

## Minimal Agent

```python
from whaagent import AgentBase, AgentRegistry

@AgentRegistry.register("hello")
class HelloAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You are a friendly greeting assistant."

# Run it
import asyncio

async def main():
    agent = HelloAgent()
    result = await agent.run("Hello!")
    print(result)

asyncio.run(main())
```

## With Custom Configuration

```python
from whaagent import AgentBase, AgentRegistry

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

## With External Prompt

```python
from whaagent import AgentBase, AgentRegistry, load_prompt

@AgentRegistry.register("custom")
class CustomAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        prompt = load_prompt("custom")
        return prompt or "Default prompt"
```

Create `prompts/custom.md`:
```markdown
You are a specialized assistant.

## Capabilities
- [list capabilities]

## Guidelines
- [list guidelines]
```

## Running from CLI

```bash
# After registering the agent
whaagent hello -i "Good morning!"
whaagent creative -i "Write a poem about coding"
whaagent custom -i "Help me with something"
```

## See Also

- [Custom Agents](../agents/custom.md) - Full custom agent guide
- [Prompts](../agents/prompts.md) - Prompt management
- [With Tools](with-tools.md) - Adding tools to agents
