---
name: whaagent-add-tool
description: Scaffold a new whaagent tool with tool.py, test file, and __init__.py export
disable-model-invocation: true
---

# Add Tool Skill

Scaffold a new whaagent tool with all required files.

## Steps

1. Ask the user for:
   - **Tool name** (snake_case, e.g. `web_scraper`)
   - **Description** (what the tool does, for the LLM)
   - **Implementation details** (what logic the tool should perform)

2. Create `src/whaagent/tools/{name}.py` using this template:

```python
from typing import Any

from whaagent.interfaces.base import Tool


class {ClassName}Tool(Tool):
    """Tool description with Google-style docstring."""

    @property
    def name(self) -> str:
        return "{tool_name}"

    @property
    def description(self) -> str:
        return "Tool description for LLM consumption."

    def invoke(self, input_str: str) -> Any:
        """Execute tool logic.

        Args:
            input_str: The input string from the LLM.

        Returns:
            Result string, or "Error: ..." on failure.
        """
        try:
            # TODO: implement tool logic
            result = input_str
            return str(result)
        except Exception as e:
            return f"Error: {e}"
```

Where `{ClassName}` is the name converted to PascalCase (e.g. `web_scraper` -> `WebScraper`).

3. Add the export to `src/whaagent/tools/__init__.py`:
   - Add import: `from .{name} import {ClassName}Tool`
   - Add to `__all__` list: `"{ClassName}Tool"`

4. Create `tests/test_{name}.py` with basic tests:

```python
"""Tests for the {name} tool."""
from whaagent.tools.{name} import {ClassName}Tool


def test_tool_import():
    """Test that the tool can be imported."""
    assert {ClassName}Tool is not None


def test_tool_name():
    """Test that the tool has the correct name."""
    tool = {ClassName}Tool()
    assert tool.name == "{tool_name}"


def test_tool_invoke_returns_string():
    """Test that invoke returns a string."""
    tool = {ClassName}Tool()
    result = tool.invoke("test input")
    assert isinstance(result, str)
```

5. Run `make check && make test` to verify everything works.

## Rules

- Tools must inherit from `Tool` ABC in `interfaces/base.py`
- Must implement `name`, `description` properties and `invoke()` method
- Tools return error strings — **never raise exceptions** from tools
- All tools use Google-style docstrings and type hints
- Export from `tools/__init__.py` is required

## Reference

Existing tools:
- `CalculatorTool` (`example.py`) — safe math evaluation via AST
- `WeatherTool` (`example.py`) — mock weather tool
- `CodeSearcher` (`code_searcher.py`) — ripgrep wrapper
- `GitCommandTool` (`git_command.py`) — git operations
- `YouTubeTranscriptTool` (`youtube_transcript.py`) — transcript fetcher
- `SyntaxValidator` (`syntax_validator.py`) — tree-sitter validation
- `AgentInvocationTool` (`agent_invocation.py`) — invoke other agents
