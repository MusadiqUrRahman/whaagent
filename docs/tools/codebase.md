# Codebase Tools

Tools for exploring, reading, and editing codebases.

## CodeSearcher

Ripgrep-based code search for fast pattern matching.

```python
from whaagent.tools import CodeSearcher

searcher = CodeSearcher("/path/to/project")
results = searcher.invoke("def authenticate")
```

### Properties
- **name**: `code_search`
- **description**: Search code using ripgrep

### Input
Regex pattern to search for.

### Output
Matching files with line numbers and context.

### Example Output
```
src/auth.py:
  45: def authenticate(user: str, password: str) -> bool:
  46:     """Authenticate a user."""

src/api/login.py:
  12:     if authenticate(username, password):
```

---

## FileFinderTool

Find files by name pattern.

```python
from whaagent.tools import FileFinderTool

finder = FileFinderTool("/path/to/project")
files = finder.invoke("*.py")
```

### Properties
- **name**: `file_finder`
- **description**: Find files matching a pattern

### Input
Glob pattern (e.g., `*.py`, `**/test_*.py`)

### Output
List of matching file paths.

---

## StructureExplorerTool

Explore directory structure.

```python
from whaagent.tools import StructureExplorerTool

explorer = StructureExplorerTool("/path/to/project")
structure = explorer.invoke("src")
```

### Properties
- **name**: `structure_explorer`
- **description**: Explore directory structure

### Input
Directory path to explore (optional, defaults to root)

### Output
Tree-like structure of directories and files.

### Example Output
```
src/
├── auth/
│   ├── __init__.py
│   └── login.py
├── api/
│   ├── __init__.py
│   └── routes.py
└── main.py
```

---

## FileOutlinerTool

Get an overview of a file's structure.

```python
from whaagent.tools import FileOutlinerTool

outliner = FileOutlinerTool("/path/to/project")
outline = outliner.invoke("src/auth/login.py")
```

### Properties
- **name**: `file_outliner`
- **description**: Get file structure outline

### Input
Path to the file.

### Output
Structure including classes, functions, imports.

### Example Output
```
File: src/auth/login.py

Imports:
  - os
  - from typing import Optional

Classes:
  - LoginManager
    - __init__(self, config: Config)
    - authenticate(self, user: str) -> bool
    - logout(self) -> None

Functions:
  - create_session(user_id: int) -> Session
  - validate_token(token: str) -> Optional[dict]
```

---

## FileFragmentReaderTool

Read specific sections of files.

```python
from whaagent.tools import FileFragmentReaderTool

reader = FileFragmentReaderTool("/path/to/project")
content = reader.invoke("src/auth.py:45-60")
```

### Properties
- **name**: `file_fragment_reader`
- **description**: Read file sections by line range

### Input
File path with optional line range: `path/to/file.py:start-end`

### Output
Content of the specified lines.

### Example
```python
# Read lines 45-60
reader.invoke("src/auth.py:45-60")

# Read entire file
reader.invoke("src/auth.py")
```

---

## FileEditorTool

Safely edit files with validation.

```python
from whaagent.tools import FileEditorTool

editor = FileEditorTool("/path/to/project")
result = editor.invoke("src/auth.py:45:old_text:new_text")
```

### Properties
- **name**: `file_editor`
- **description**: Edit files with search and replace

### Input
Edit specification: `path:line:old_text:new_text`

### Output
Success message or error description.

### Safety Features
- Validates file exists
- Checks for exact match before replacing
- Returns error if old_text not found

---

## SyntaxValidator

Validate code syntax using Tree-sitter.

```python
from whaagent.tools import SyntaxValidator

validator = SyntaxValidator()
result = validator.invoke("python:def foo():\n    return 1")
```

### Properties
- **name**: `syntax_validator`
- **description**: Validate code syntax

### Input
Format: `language:code`

### Output
Validation result with any errors.

### Supported Languages
- Python
- JavaScript
- TypeScript
- Go
- Rust
- Java
- And more...

---

## Usage in Agents

```python
from typing import Sequence, Any
from langchain_core.tools import StructuredTool
from whaagent import AgentBase, AgentRegistry
from whaagent.tools import (
    CodeSearcher,
    FileFinderTool,
    StructureExplorerTool,
    FileOutlinerTool,
    FileFragmentReaderTool,
    FileEditorTool,
)

@AgentRegistry.register("code-master")
class CodeMasterAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You are a code exploration and editing assistant."

    def local_tools(self) -> Sequence[Any]:
        root = "/path/to/project"
        return [
            StructuredTool.from_function(
                func=CodeSearcher(root).invoke,
                name="code_search",
                description="Search code using ripgrep",
            ),
            StructuredTool.from_function(
                func=FileFinderTool(root).invoke,
                name="file_finder",
                description="Find files matching a pattern",
            ),
            # ... other tools
        ]
```

## See Also

- [Tools Overview](index.md) - All available tools
- [Custom Agents](../agents/custom.md) - Using tools in agents
