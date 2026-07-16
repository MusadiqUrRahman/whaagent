# Tools

Tools extend agent capabilities with specific functions.

## Tool Types

### Local Tools
Python-based tools that run locally without external dependencies.

### MCP Tools
Tools provided by MCP (Model Context Protocol) servers.

## Available Local Tools

| Tool | Description |
|------|-------------|
| [CodeSearcher](codebase.md#codesearcher) | Ripgrep-based code search |
| [FileFinderTool](codebase.md#filefindertool) | Find files by pattern |
| [StructureExplorerTool](codebase.md#structureexplorertool) | Explore directory structure |
| [FileOutlinerTool](codebase.md#fileoutlinertool) | Get file overview |
| [FileFragmentReaderTool](codebase.md#filefragmentreadertool) | Read file sections |
| [FileEditorTool](codebase.md#fileeditortool) | Edit files safely |
| [YouTubeTranscriptTool](youtube.md) | Extract video transcripts |
| [SyntaxValidator](codebase.md#syntaxvalidator) | Validate code syntax |

## Using Tools

### In Custom Agents

```python
from typing import Sequence, Any
from whaagent import AgentBase, AgentRegistry
from whaagent.tools import CodeSearcher, FileFinderTool

@AgentRegistry.register("code-analyst")
class CodeAnalystAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You analyze codebases."

    def local_tools(self) -> Sequence[Any]:
        return [
            CodeSearcher("."),
            FileFinderTool("."),
        ]
```

### Tool Configuration

Some tools accept configuration:

```python
from whaagent.tools import CodeSearcher

# Custom root directory
searcher = CodeSearcher("/path/to/project")

# Use in agent
def local_tools(self) -> Sequence[Any]:
    return [CodeSearcher(self.config.agents.defaults.get("project_root", "."))]
```

## Creating Custom Tools

### Using StructuredTool

```python
from langchain_core.tools import StructuredTool

def my_function(input_text: str) -> str:
    """Description of what the tool does."""
    return f"Processed: {input_text}"

tool = StructuredTool.from_function(
    func=my_function,
    name="my_tool",
    description="What this tool does",
)
```

### Custom Tool Class

```python
from whaagent.interfaces.base import Tool

class MyCustomTool(Tool):
    @property
    def name(self) -> str:
        return "my_custom_tool"

    @property
    def description(self) -> str:
        return "Description of the tool"

    def invoke(self, input_str: str) -> str:
        """Execute the tool.

        Args:
            input_str: Input for the tool

        Returns:
            Result as a string (never raise exceptions)
        """
        try:
            # Tool logic here
            return "Result"
        except Exception as e:
            return f"Error: {e}"
```

## Tool Best Practices

### Error Handling
Tools should return error strings, not raise exceptions:

```python
# Good
def invoke(self, input_str: str) -> str:
    try:
        result = do_something(input_str)
        return result
    except FileNotFoundError:
        return f"Error: File '{input_str}' not found."

# Bad
def invoke(self, input_str: str) -> str:
    if not os.path.exists(input_str):
        raise FileNotFoundError(f"File not found")
```

### Descriptive Names and Descriptions

```python
@property
def name(self) -> str:
    return "search_python_files"  # Clear and specific

@property
def description(self) -> str:
    return """Search for patterns in Python files.
    Input: A regex pattern to search for.
    Output: Matching files and lines."""
```

## See Also

- [Codebase Tools](codebase.md) - File and code operations
- [YouTube Tool](youtube.md) - Video transcripts
- [MCP Servers](../mcp/index.md) - External tools via MCP
