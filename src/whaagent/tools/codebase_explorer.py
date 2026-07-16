import fnmatch
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from whaagent.interfaces.base import Tool

# Language detection by file extension
LANGUAGE_EXTENSIONS: Dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".php": "php",
}

# Regex patterns for each language
# Each pattern captures relevant code construct
LANGUAGE_PATTERNS: Dict[str, List[str]] = {
    "python": [
        r"^\s*(class\s+\w+.*?)[:\(]",
        r"^\s*(async\s+def\s+\w+.*?)\(",
        r"^\s*(def\s+\w+.*?)\(",
    ],
    "javascript": [
        r"^\s*(export\s+)?(default\s+)?(class\s+\w+)",
        r"^\s*(export\s+)?(default\s+)?(function\s*\*?\s+\w+)",
        r"^\s*(export\s+)?(default\s+)?(const\s+\w+\s*=\s*\([^)]*\)\s*=>)",
        r"^\s*(export\s+)?(default\s+)?(const\s+\w+\s*=\s*async\s*\([^)]*\)\s*=>)",
    ],
    "typescript": [
        r"^\s*(export\s+)?(default\s+)?(class\s+\w+)",
        r"^\s*(export\s+)?(default\s+)?(function\s*\*?\s+\w+)",
        r"^\s*(export\s+)?(default\s+)?(const\s+\w+\s*=\s*\([^)]*\)\s*=>)",
        r"^\s*(export\s+)?(default\s+)?(const\s+\w+\s*=\s*async\s*\([^)]*\)\s*=>)",
        r"^\s*(export\s+)?(interface\s+\w+)",
        r"^\s*(export\s+)?(type\s+\w+)",
        r"^\s*(export\s+)?(enum\s+\w+)",
        r"^\s*(export\s+)?(abstract\s+class\s+\w+)",
        r"^\s*(export\s+)?(namespace\s+\w+)",
    ],
    "rust": [
        r"^\s*(pub\s+(\([^)]+\)\s+)?)?(struct\s+\w+)",
        r"^\s*(pub\s+)?(enum\s+\w+)",
        r"^\s*(pub\s+)?(trait\s+\w+)",
        r"^\s*(pub\s+(\([^)]+\)\s+)?)?(async\s+)?(fn\s+\w+)",
        r"^\s*(impl\s+(<[^>]+>\s+)?\w+)",
        r"^\s*(pub\s+)?(mod\s+\w+)",
    ],
    "go": [
        r"^\s*func\s+\(\w+\s+\*?\w+\)\s*\w+",  # method with receiver
        r"^\s*func\s+\w+",  # function
        r"^\s*type\s+\w+\s+struct\b",
        r"^\s*type\s+\w+\s+interface\b",
        r"^\s*type\s+\w+\s+func\b",
        r"^\s*type\s+\w+\s*\(",  # type alias with params
    ],
    "java": [
        r"^\s*(public|private|protected)?\s*(abstract\s+)?(class\s+\w+)",
        r"^\s*(public\s+)?(interface\s+\w+)",
        r"^\s*(public\s+)?(enum\s+\w+)",
        r"^\s*@\w+(\([^)]*\))?\s*$",  # annotations (standalone)
        r"^\s*(public|private|protected)\s+(static\s+)?[\w<>?,\s]+\s+\w+\s*\(",  # methods
        r"^\s*(public|private|protected)\s+\w+\s*\([^\)]*\)\s*\{",  # constructors
    ],
    "c": [
        r"^\s*(typedef\s+)?(struct\s+\w*)",
        r"^\s*(typedef\s+)?(enum\s+\w*)",
        r"^\s*(typedef\s+)?(union\s+\w*)",
        r"^\s*(void|int|char|float|double|long|unsigned|signed|short)\s+[\w\s\*]+\s*\w+\s*\(",
    ],
    "cpp": [
        r"^\s*(typedef\s+)?(struct\s+\w*)",
        r"^\s*(typedef\s+)?(enum\s+\w*)",
        r"^\s*(typedef\s+)?(union\s+\w*)",
        r"^\s*(class\s+\w+)",
        r"^\s*(namespace\s+\w+)",
        r"^\s*(template\s*<[^>]*>)?\s*class\s+\w+",  # template class
        r"^\s*(template\s*<[^>]*>)?\s*[\w:]+\s+[\w:]+\s*\(",  # template function
    ],
    "php": [
        r"^\s*(abstract\s+)?(final\s+)?(class\s+\w+)",
        r"^\s*(interface\s+\w+)",
        r"^\s*(trait\s+\w+)",
        r"^\s*(public|private|protected)?\s*(static\s+)?function\s+\w+",
    ],
}


class CodebaseExplorer:
    """
    A utility for agents to discover and navigate codebases.
    Base class for specific codebase tools.
    """

    def __init__(self, root_dir: Union[str, Path], ignore_patterns: Optional[List[str]] = None):
        self.root_dir = Path(root_dir).resolve()
        # Standard noise reduction for agentic context
        self.ignore_patterns = ignore_patterns or [
            ".git",
            "__pycache__",
            "node_modules",
            ".venv",
            "dist",
            "build",
            ".mypy_cache",
            ".pytest_cache",
        ]

    def _is_ignored(self, path: Path) -> bool:
        try:
            # Resolve symlinks to handle macOS /var -> /private/var symlink
            resolved_path = path.resolve()
            rel_path = str(resolved_path.relative_to(self.root_dir.resolve()))
        except ValueError:
            return True
        # Check each path segment against ignore patterns
        parts = Path(rel_path).parts
        for part in parts:
            for pattern in self.ignore_patterns:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False


class StructureExplorerTool(CodebaseExplorer, Tool):
    """Tool to discover the directory structure of a project."""

    @property
    def name(self) -> str:
        return "discover_structure"

    @property
    def description(self) -> str:
        return "Lists files and directories recursively up to a certain depth. Helps understand project layout."

    def invoke(self, input_str: str) -> Any:
        # Input can be max_depth as string, defaults to 3
        try:
            max_depth = int(input_str) if input_str.isdigit() else 3
        except Exception:
            max_depth = 3
        return self._build_tree(self.root_dir, depth=0, max_depth=max_depth)

    def _build_tree(self, current_dir: Path, depth: int, max_depth: int) -> Dict[str, Any]:
        tree: Dict[str, Any] = {"name": current_dir.name or str(current_dir), "type": "directory", "children": []}

        if depth >= max_depth:
            return tree

        try:
            for item in sorted(current_dir.iterdir()):
                if self._is_ignored(item):
                    continue

                if item.is_dir():
                    tree["children"].append(self._build_tree(item, depth + 1, max_depth))
                else:
                    tree["children"].append(
                        {"name": item.name, "type": "file", "size_kb": round(item.stat().st_size / 1024, 2)}
                    )
        except PermissionError:
            tree["error"] = "Permission denied"

        return tree


class FileOutlinerTool(CodebaseExplorer, Tool):
    """Tool to extract high-level signatures from various programming language files."""

    @property
    def name(self) -> str:
        return "get_file_outline"

    @property
    def description(self) -> str:
        return """Extracts classes, functions, and other definitions from code files.
        Supports: Python, JavaScript, TypeScript, Rust, Go, Java, C/C++, PHP.
        Returns a list of signatures with their line numbers.
        Output format: [{"line": 15, "signature": "class MyAgent:"}, ...]"""

    def invoke(self, file_path: str) -> Any:
        full_path = self.root_dir / file_path
        if not full_path.exists() or not full_path.is_file():
            return f"Error: File {file_path} not found."

        language = self._detect_language(file_path)
        if language is None:
            return f"Error: Unsupported file type for {file_path}. Supported: Python, JS/TS, Rust, Go, Java, C/C++, PHP"

        patterns = LANGUAGE_PATTERNS.get(language, [])
        return self._extract_outline(full_path, patterns)

    def _detect_language(self, file_path: str) -> Optional[str]:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        return LANGUAGE_EXTENSIONS.get(ext)

    def _extract_outline(self, file_path: Path, patterns: List[str]) -> List[Dict[str, Any]]:
        """Extract code outline using regex patterns."""
        outline: List[Dict[str, Any]] = []
        compiled_patterns = [re.compile(p) for p in patterns]

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, 1):
                    for pattern in compiled_patterns:
                        if pattern.search(line):
                            # Clean up signature (limit length for readability)
                            signature = line.strip()
                            if len(signature) > 100:
                                signature = signature[:97] + "..."
                            outline.append({"line": line_num, "signature": signature})
                            break  # Only match first pattern per line
            return outline
        except Exception as e:
            return [{"error": f"Error reading file: {e}"}]


class FileFragmentReaderTool(CodebaseExplorer, Tool):
    """Tool to read a specific range of a file."""

    @property
    def name(self) -> str:
        return "read_file_fragment"

    @property
    def description(self) -> str:
        return "Reads a specific line range from a file. Input format: 'path:start:end' (e.g. 'src/cli.py:1:20')."

    def invoke(self, input_str: str) -> Any:
        try:
            parts = input_str.split(":")
            if len(parts) < 3:
                return "Error: Invalid input format. Use 'path:start:end'."
            file_path = ":".join(parts[:-2])
            start_line = int(parts[-2])
            end_line = int(parts[-1])

            full_path = self.root_dir / file_path
            if not full_path.exists():
                return f"Error: File {file_path} not found."

            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                return "".join(lines[max(0, start_line - 1) : end_line])
        except Exception as e:
            return f"Error: {e}"


class FileFinderTool(CodebaseExplorer, Tool):
    """Tool to find files by name using 'fd'."""

    @property
    def name(self) -> str:
        return "find_files"

    @property
    def description(self) -> str:
        return (
            "Fast file search by name using 'fd'. Returns paths relative to project root. "
            "Input is a search pattern (regex or simple string)."
        )

    def invoke(self, pattern: str) -> Any:
        try:
            # First, get candidates using fd
            # -H: hidden files, -I: ignore .gitignore for faster full list if needed,
            # but usually we want to respect it, so let's stick to standard fd.
            # We'll list all files and let fzf rank them.
            fd_cmd = ["fd", "--color", "never", "-H", ".", str(self.root_dir)]
            fd_result = subprocess.run(fd_cmd, capture_output=True, text=True, check=False)

            if fd_result.returncode != 0:
                if fd_result.stderr:
                    return f"Error executing fd: {fd_result.stderr}"
                return "No matches found"

            all_files = fd_result.stdout
            if not all_files:
                return "No matches found"

            # Use fzf to rank the files based on the pattern
            # fzf -f performs a non-interactive fuzzy search
            try:
                fzf_cmd = ["fzf", "-f", pattern]
                fzf_result = subprocess.run(fzf_cmd, input=all_files, capture_output=True, text=True, check=False)
                if fzf_result.returncode == 0:
                    ranked_files = fzf_result.stdout.splitlines()
                else:
                    # Fallback to simple substring match if fzf returns nothing or fails
                    ranked_files = [f for f in all_files.splitlines() if pattern.lower() in f.lower()]
            except FileNotFoundError:
                # Fallback if fzf is missing
                ranked_files = [f for f in all_files.splitlines() if pattern.lower() in f.lower()]

            # Convert absolute paths back to relative and limit results
            relative_files = []
            for f in ranked_files[:30]:  # Limit to top 30
                try:
                    relative_files.append(str(Path(f).relative_to(self.root_dir)))
                except ValueError:
                    relative_files.append(f)

            if not relative_files:
                return "No matches found for the given pattern."

            return relative_files
        except FileNotFoundError:
            return "Error: Required search tools (fd) not found."


class FileEditorTool(CodebaseExplorer, Tool):
    """Tool to safely edit files with line-based operations."""

    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB hard limit
    WARN_FILE_SIZE = 500 * 1024  # 500KB warning threshold

    # Binary file extensions to reject
    BINARY_EXTENSIONS = {
        ".pyc",
        ".pyo",
        ".so",
        ".dll",
        ".dylib",
        ".exe",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".7z",
        ".rar",
        ".mp3",
        ".mp4",
        ".wav",
        ".avi",
        ".mov",
        ".db",
        ".sqlite",
        ".sqlite3",
    }

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return """Edit files with line-based or text-based operations.

Line-based operations (colon-delimited):
- replace:path:start:end:content - Replace lines start to end
- insert:path:after_line:content - Insert after line number
- insert:path:before_line:content - Insert before line number
- delete:path:start:end - Delete lines start to end

Text-based operation (JSON format, RECOMMENDED):
{"op": "search_replace", "path": "file.py", "old": "exact text to find", "new": "replacement text"}

The search_replace operation finds exact text and replaces it. No line numbers needed.
The old text must be unique in the file.

IMPORTANT: Always read the file first using read_file_fragment to verify content before editing.
Line numbers are 1-indexed. Content uses \\n for newlines.
"""

    def invoke(self, input_str: str) -> Any:
        """Parse and execute edit operation."""
        try:
            stripped = input_str.strip()
            if stripped.startswith("{"):
                return self._handle_json_input(stripped)
            return self._handle_delimited_input(stripped)
        except Exception as e:
            return f"Error: {e}"

    def _handle_json_input(self, input_str: str) -> Any:
        """Handle JSON-formatted input for complex content."""
        import json

        data = json.loads(input_str)
        op = data.get("op")
        path = data.get("path")
        content = data.get("content", "")

        if op == "replace":
            return self._replace_lines(path, data["start"], data["end"], content)
        elif op == "search_replace":
            return self._search_replace(path, data["old"], data.get("new", ""))
        elif op == "insert":
            return self._insert_lines(path, data.get("after"), data.get("before"), content)
        elif op == "delete":
            return self._delete_lines(path, data["start"], data["end"])
        else:
            return f"Error: Unknown operation '{op}'. Supported: replace, search_replace, insert, delete"

    def _handle_delimited_input(self, input_str: str) -> Any:
        """Handle colon-delimited input format."""
        op = input_str.split(":", 1)[0]

        if op == "replace":
            # Format: replace:path:start:end:content
            parts = input_str.split(":", 4)
            if len(parts) < 5:
                return "Error: Replace format: 'replace:path:start:end:content'"
            path = parts[1]
            start = int(parts[2])
            end = int(parts[3])
            content = parts[4].replace("\\n", "\n")
            return self._replace_lines(path, start, end, content)

        elif op == "insert":
            # Format: insert:path:position:content
            parts = input_str.split(":", 3)
            if len(parts) < 4:
                return "Error: Insert format: 'insert:path:position:content'"
            path = parts[1]
            position = parts[2]
            content = parts[3].replace("\\n", "\n")

            if position.isdigit():
                return self._insert_lines(path, after=int(position), before=None, content=content)
            elif position.startswith("before_"):
                line_num = int(position[7:])
                return self._insert_lines(path, after=None, before=line_num, content=content)
            else:
                return f"Error: Invalid insert position '{position}'"

        elif op == "delete":
            # Format: delete:path:start:end
            parts = input_str.split(":", 3)
            if len(parts) < 4:
                return "Error: Delete format: 'delete:path:start:end'"
            path = parts[1]
            start = int(parts[2])
            end = int(parts[3])
            return self._delete_lines(path, start, end)

        else:
            return f"Error: Unknown operation '{op}'"

    def _replace_lines(self, path: str, start: int, end: int, content: str) -> str:
        """Replace lines start to end (1-indexed) with content."""
        full_path = self._validate_path(path)

        if not full_path.exists():
            return f"Error: File '{path}' not found"

        warning = self._check_file_size(full_path)

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            return f"Error: File '{path}' is not valid UTF-8 text"

        self._validate_line_bounds(lines, start, end, path)

        new_lines = lines[: start - 1]
        new_lines.append(content if content.endswith("\n") else content + "\n")
        new_lines.extend(lines[end:])

        new_content = "".join(new_lines)
        self._atomic_write(full_path, new_content)

        result = f"Replaced lines {start}-{end} in '{path}'"
        if warning:
            result = f"{warning}\n{result}"

        # Validate syntax after edit
        syntax_warning = self._validate_syntax(new_content, path)
        if syntax_warning:
            result = f"{result}{syntax_warning}"

        return result

    def _insert_lines(self, path: str, after: Optional[int], before: Optional[int], content: str) -> str:
        """Insert content after or before a specific line."""
        full_path = self._validate_path(path)

        if not full_path.exists():
            return f"Error: File '{path}' not found"

        warning = self._check_file_size(full_path)

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            return f"Error: File '{path}' is not valid UTF-8 text"

        insert_content = content if content.endswith("\n") else content + "\n"

        if before is not None:
            if before < 1:
                return f"Error: before_line must be >= 1, got {before}"
            if before > len(lines) + 1:
                return f"Error: before_line ({before}) exceeds file length + 1 ({len(lines) + 1})"
            insert_pos = before - 1
            position_desc = f"before line {before}"
        else:
            if after is None:
                after = 0
            if after < 0:
                return f"Error: after_line must be >= 0, got {after}"
            if after > len(lines):
                return f"Error: after_line ({after}) exceeds file length ({len(lines)})"
            insert_pos = after
            position_desc = f"after line {after}" if after > 0 else "at beginning"

        new_lines = lines[:insert_pos] + [insert_content] + lines[insert_pos:]
        new_content = "".join(new_lines)

        self._atomic_write(full_path, new_content)

        result = f"Inserted content {position_desc} in '{path}'"
        if warning:
            result = f"{warning}\n{result}"

        # Validate syntax after edit
        syntax_warning = self._validate_syntax(new_content, path)
        if syntax_warning:
            result = f"{result}{syntax_warning}"

        return result

    def _delete_lines(self, path: str, start: int, end: int) -> str:
        """Delete lines start to end (1-indexed)."""
        full_path = self._validate_path(path)

        if not full_path.exists():
            return f"Error: File '{path}' not found"

        warning = self._check_file_size(full_path)

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            return f"Error: File '{path}' is not valid UTF-8 text"

        self._validate_line_bounds(lines, start, end, path)

        new_lines = lines[: start - 1] + lines[end:]
        new_content = "".join(new_lines)

        self._atomic_write(full_path, new_content)

        deleted_count = end - start + 1
        result = f"Deleted {deleted_count} line(s) ({start}-{end}) from '{path}'"
        if warning:
            result = f"{warning}\n{result}"

        # Validate syntax after edit
        syntax_warning = self._validate_syntax(new_content, path)
        if syntax_warning:
            result = f"{result}{syntax_warning}"

        return result

    def _search_replace(self, path: str, old_text: str, new_text: str) -> str:
        """Find and replace exact text in a file.

        More robust than line-based editing because it doesn't require line numbers.
        Fails if old_text is not found or found multiple times.

        Args:
            path: Relative path to the file
            old_text: Exact text to find (must be unique in the file)
            new_text: Text to replace with

        Returns:
            Success message or error with helpful context
        """
        full_path = self._validate_path(path)

        if not full_path.exists():
            return f"Error: File '{path}' not found. Use find_files to locate the file."

        warning = self._check_file_size(full_path)

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            return f"Error: File '{path}' is not valid UTF-8 text"

        # Count exact matches
        count = content.count(old_text)

        if count == 0:
            return self._format_search_error(content, old_text, path)

        if count > 1:
            return (
                f"Error: Found {count} occurrences of the search text in '{path}'. "
                f"Make the search text more specific by including more context lines.\n"
                f"Tip: Use read_file_fragment to see the file and identify unique context."
            )

        # Perform replacement
        new_content = content.replace(old_text, new_text, 1)

        self._atomic_write(full_path, new_content)

        # Find line numbers for reporting
        char_pos = content.index(old_text)
        lines_before = content[:char_pos].count("\n") + 1
        lines_in_old = old_text.count("\n")
        end_line = lines_before + lines_in_old

        result = f"Replaced text at lines {lines_before}-{end_line} in '{path}'"
        if warning:
            result = f"{warning}\n{result}"

        # Validate syntax after edit
        syntax_warning = self._validate_syntax(new_content, path)
        if syntax_warning:
            result = f"{result}{syntax_warning}"

        return result

    def _format_search_error(self, content: str, old_text: str, path: str) -> str:
        """Format helpful error message when search text is not found."""
        # Try to find similar text
        old_lines = old_text.strip().split("\n")
        if old_lines:
            first_line = old_lines[0].strip()
            if len(first_line) > 10:  # Only search if first line is meaningful
                for i, line in enumerate(content.split("\n"), 1):
                    if first_line in line:
                        return (
                            f"Error: Search text not found exactly in '{path}'.\n"
                            f"Found similar text at line {i}:\n"
                            f"  {line.strip()[:60]}{'...' if len(line.strip()) > 60 else ''}\n"
                            f"Tip: Use read_file_fragment('{path}:{max(1, i - 2)}:{i + 2}') "
                            f"to see the exact content."
                        )

        return (
            f"Error: Search text not found in '{path}'.\n"
            f"Tip: Use read_file_fragment to view the file content first, "
            f"then copy the exact text to replace."
        )

    def _validate_path(self, path: str) -> Path:
        """Validate and resolve path within root_dir."""
        full_path = (self.root_dir / path).resolve()

        if not str(full_path).startswith(str(self.root_dir.resolve())):
            raise ValueError(f"Path '{path}' is outside of project root")

        if self._is_ignored(full_path):
            raise ValueError(f"Path '{path}' is in an ignored directory")

        if full_path.suffix.lower() in self.BINARY_EXTENSIONS:
            raise ValueError(f"Cannot edit binary file: {path}")

        return full_path

    def _validate_line_bounds(self, lines: List[str], start: int, end: int, path: str = "file") -> None:
        """Validate line numbers are within bounds with helpful error messages."""
        total_lines = len(lines)

        if start < 1:
            raise ValueError(
                f"Start line must be >= 1, got {start}. Line numbers are 1-indexed. "
                f"Use read_file_fragment to verify line numbers."
            )
        if end < start:
            raise ValueError(
                f"End line ({end}) must be >= start line ({start}). "
                f"Use read_file_fragment('{path}:{start}:{start + 5}') to see the content."
            )
        if start > total_lines:
            raise ValueError(
                f"Start line ({start}) exceeds file length ({total_lines} lines). "
                f"Use read_file_fragment('{path}:{max(1, total_lines - 5)}:{total_lines}') "
                f"to see the end of the file."
            )
        if end > total_lines + 1:
            raise ValueError(
                f"End line ({end}) exceeds file length + 1 ({total_lines + 1}). "
                f"Use read_file_fragment to verify line numbers before editing."
            )

    def _check_file_size(self, path: Path) -> Optional[str]:
        """Check file size and return warning if large."""
        size = path.stat().st_size
        if size > self.MAX_FILE_SIZE:
            raise ValueError(f"File too large ({size} bytes). Maximum is {self.MAX_FILE_SIZE}")
        if size > self.WARN_FILE_SIZE:
            return f"Warning: Large file ({size} bytes). Proceeding with edit."
        return None

    def _atomic_write(self, path: Path, content: str) -> None:
        """Write content atomically using temp file + rename."""
        import os
        import tempfile

        dir_path = path.parent
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, prefix=".tmp_edit_")

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _validate_syntax(self, content: str, path: str) -> Optional[str]:
        """Validate the syntax of the content after an edit.

        Args:
            content: The file content after the edit
            path: The file path (used for language detection)

        Returns:
            Warning message if there are syntax errors, None otherwise
        """
        from whaagent.tools.syntax_validator import get_validator

        result = get_validator().validate(content, path)
        return result.warning_message
