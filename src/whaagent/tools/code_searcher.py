import subprocess
from typing import Any, List, Union

from whaagent.interfaces.base import Tool


class CodeSearcher(Tool):
    """Wraps ripgrep (rg) for ultra-fast codebase querying."""

    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    @property
    def name(self) -> str:
        return "code_search"

    @property
    def description(self) -> str:
        return "Searches the codebase for a given pattern using ripgrep. Returns top 20 matches."

    def invoke(self, input_str: str) -> Any:
        """Executes a search across the codebase. input_str is search query."""
        return self.grep_search(input_str)

    def grep_search(self, query: str, glob: str = "*") -> Union[List[str], str]:
        """
        Executes a search across the codebase using ripgrep.
        Returns matches in vimgrep format (file:line:col:text).
        """
        try:
            # --vimgrep: file:line:col:text
            # --smart-case: case-insensitive unless query has uppercase
            # --iglob: filter by glob pattern
            # --max-columns: limit long lines to avoid token blowup
            cmd = ["rg", "--vimgrep", "--smart-case", "--max-columns", "500", "--iglob", glob, query, self.root_dir]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if result.returncode == 0:
                lines = result.stdout.splitlines()
                if not lines:
                    return "No matches found."
                return lines[:30]  # Increased to 30 for more context

            if result.stderr:
                return f"Error executing rg: {result.stderr}"
            return "No matches found."

        except FileNotFoundError:
            return "Error: ripgrep (rg) is not installed. Please install it to use this tool."
