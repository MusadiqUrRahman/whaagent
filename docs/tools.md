# Local Tools

This document provides detailed information about all local tools available in the Agentic Framework.

## Tool Overview

| Tool | Capability | Example |
|------|------------|---------|
| `find_files` | Fast search via `fd` | `*.py` finds Python files |
| `discover_structure` | Directory tree mapping | Understands project layout |
| `get_file_outline` | AST signature parsing (Python, TS, Go, Rust, Java, C++, PHP) | Extracts classes/functions |
| `read_file_fragment` | Precise file reading | `file.py:10:50` |
| `code_search` | Fast search via `ripgrep` | Global regex search |
| `edit_file` | Safe file editing | Inserts/Replaces lines |

---

## find_files

Fast file search using the `fd` tool.

### Description
Recursively searches for files matching a pattern in the project directory.

### Parameters
- `pattern`: Glob pattern to match (e.g., `*.py`, `test_*.ts`)

### Example
```bash
# Find all Python files
find_files "*.py"

# Find test files
find_files "test_*.py"
```

---

## discover_structure

Maps the directory structure of the project.

### Description
Provides a tree-like view of the project's directory structure, helping agents understand the codebase layout.

### Parameters
- `path`: Optional starting path (defaults to project root)
- `max_depth`: Maximum depth to explore (default: 3)

### Example
```bash
# Discover full project structure
discover_structure()

# Discover specific directory
discover_structure("src/", max_depth=2)
```

---

## get_file_outline

Extracts code signatures using AST parsing.

### Description
Parses source files and extracts classes, functions, methods, and their signatures. Supports multiple languages:
- Python
- TypeScript/JavaScript
- Go
- Rust
- Java
- C++
- PHP

### Parameters
- `file_path`: Path to the file to analyze

### Example
```bash
# Get outline of a Python file
get_file_outline("src/main.py")

# Output example:
# class MyClass:
#     def __init__(self, x: int) -> None
#     def process(self) -> str
# def helper_function(data: list) -> dict
```

---

## read_file_fragment

Reads specific portions of a file.

### Description
Reads a range of lines from a file, allowing precise inspection of specific code sections.

### Format
`file_path:start_line:end_line`

### Parameters
- `file_path`: Path to the file
- `start_line`: Starting line number (1-indexed)
- `end_line`: Ending line number (inclusive)

### Example
```bash
# Read lines 10-50 of a file
read_file_fragment("src/main.py:10:50")

# Read a specific function (assuming it's on lines 25-40)
read_file_fragment("src/main.py:25:40")
```

---

## code_search

Fast code search using `ripgrep`.

### Description
Performs global regex-based searches across the codebase for patterns, function names, or specific code constructs.

### Parameters
- `pattern`: Regular expression to search for
- `file_pattern`: Optional glob pattern to filter files (e.g., `*.py`)
- `context_lines`: Number of context lines to include (default: 2)

### Example
```bash
# Search for a function name
code_search("def process_data")

# Search in Python files only
code_search("database\.query", file_pattern="*.py")

# Search with more context
code_search("TODO|FIXME", context_lines=5)
```

---

## edit_file

Safe file editing with multiple operation modes.

### Description
Modifies files with safe operations including insert, replace, and delete. Supports both line-based operations and search-replace mode.

### Operation Modes

#### RECOMMENDED: `search_replace` (no line numbers needed)

Format: `{"op": "search_replace", "path": "file.py", "old": "exact text", "new": "replacement text"}`

```json
{
  "op": "search_replace",
  "path": "src/main.py",
  "old": "def old_function():\n    pass",
  "new": "def new_function():\n    return True"
}
```

#### Line-based Operations

| Operation | Format | Description |
|-----------|--------|-------------|
| `replace` | `replace:path:start:end:content` | Replace lines start through end with content |
| `insert` | `insert:path:after_line:content` | Insert content after specified line |
| `delete` | `delete:path:start:end` | Delete lines start through end |

### Examples

```bash
# Search and replace (recommended)
edit_file('{"op": "search_replace", "path": "src/main.py", "old": "old_value", "new": "new_value"}')

# Replace specific lines
edit_file("replace:src/main.py:10:15:print('new code')")

# Insert after line 20
edit_file("insert:src/main.py:20:\n# New comment\nprint('hello')")

# Delete lines 30-35
edit_file("delete:src/main.py:30:35")
```

### Safety Features
- Validates file exists before editing
- Checks line numbers are within bounds
- Preserves file permissions
- Creates backup if configured

---

## Creating Custom Tools

To add your own local tools to an agent:

```python
from langchain_core.tools import StructuredTool
from whaagent import AgentBase, AgentRegistry

@AgentRegistry.register("my-agent")
class MyAgent(LangGraphMCPAgent):
    @property
    def system_prompt(self) -> str:
        return "You are my custom agent."

    def local_tools(self) -> list:
        return [
            StructuredTool.from_function(
                func=self.my_tool,
                name="my_tool",
                description="Description of what your tool does",
            )
        ]

    def my_tool(self, input_data: str) -> str:
        # Your tool logic here
        return f"Processed: {input_data}"
```

For more details, see the [Build Your Own Agent](../README.md#️-build-your-own-agent) section in the main README.
