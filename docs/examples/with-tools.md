# Agent with Tools Example

Add local Python tools to extend agent capabilities.

## Basic Tool

```python
from typing import Sequence, Any
from langchain_core.tools import StructuredTool
from whaagent import AgentBase, AgentRegistry

def get_current_time() -> str:
    """Get the current time."""
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")

@AgentRegistry.register("time-agent")
class TimeAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You are a time assistant. Help users with time-related queries."

    def local_tools(self) -> Sequence[Any]:
        return [
            StructuredTool.from_function(
                func=get_current_time,
                name="get_current_time",
                description="Get the current time",
            )
        ]
```

## Tool with Parameters

```python
from typing import Sequence, Any
from langchain_core.tools import StructuredTool
from whaagent import AgentBase, AgentRegistry

def calculate(expression: str) -> str:
    """Safely evaluate a mathematical expression.

    Args:
        expression: A mathematical expression (e.g., "2 + 2")
    """
    import ast
    import operator

    ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }

    try:
        tree = ast.parse(expression, mode='eval')
        # Simple evaluation - only allow basic math
        result = eval(compile(tree, '<string>', 'eval'), {"__builtins__": {}}, ops)
        return str(result)
    except Exception as e:
        return f"Error: {e}"

@AgentRegistry.register("calculator")
class CalculatorAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You are a calculator assistant. Perform mathematical calculations."

    def local_tools(self) -> Sequence[Any]:
        return [
            StructuredTool.from_function(
                func=calculate,
                name="calculate",
                description="Evaluate a mathematical expression",
            )
        ]
```

## Using Built-in Tools

```python
from typing import Sequence, Any
from langchain_core.tools import StructuredTool
from whaagent import AgentBase, AgentRegistry
from whaagent.tools import CodeSearcher, FileFinderTool

@AgentRegistry.register("code-helper")
class CodeHelperAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You help with code analysis."

    def local_tools(self) -> Sequence[Any]:
        root_dir = "."
        searcher = CodeSearcher(root_dir)
        finder = FileFinderTool(root_dir)

        return [
            StructuredTool.from_function(
                func=searcher.invoke,
                name="code_search",
                description="Search for patterns in code",
            ),
            StructuredTool.from_function(
                func=finder.invoke,
                name="file_finder",
                description="Find files matching a pattern",
            ),
        ]
```

## Custom Tool Class

```python
from whaagent.interfaces.base import Tool
from whaagent import AgentBase, AgentRegistry

class WeatherTool(Tool):
    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def description(self) -> str:
        return "Get weather for a location"

    def invoke(self, input_str: str) -> str:
        # Never raise exceptions - return error strings
        try:
            # Your weather API logic here
            return f"Weather in {input_str}: Sunny, 72°F"
        except Exception as e:
            return f"Error getting weather: {e}"

@AgentRegistry.register("weather")
class WeatherAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You provide weather information."

    def local_tools(self):
        return [WeatherTool()]
```

## See Also

- [Tools Overview](../tools/index.md) - All available tools
- [Custom Agents](../agents/custom.md) - Full agent guide
- [With MCP](with-mcp.md) - Adding MCP tools
