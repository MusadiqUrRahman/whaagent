"""Git command tool for analyzing repository changes."""

import subprocess
from pathlib import Path

from whaagent.interfaces.base import Tool


class GitCommandTool(Tool):
    """Execute git commands to analyze repository changes.

    Only whitelisted git commands are supported for security.
    All commands are executed with subprocess.run() using list arguments.
    """

    # Whitelist of allowed git subcommands
    ALLOWED_COMMANDS = {"status", "diff", "log", "show", "branch"}

    def __init__(self, repo_path: str | None = None):
        """Initialize git tool.

        Args:
            repo_path: Path to git repository. Defaults to current directory.
        """
        self.repo_path = repo_path or str(Path.cwd())

    @property
    def name(self) -> str:
        return "git_command"

    @property
    def description(self) -> str:
        return "Execute git commands (status, diff, log, show, branch) to analyze repository changes"

    def invoke(self, input_str: str) -> str:
        """Execute a git command.

        Args:
            input_str: Git command (e.g., "status", "diff --cached", "log -5")

        Returns:
            Command output or error message
        """
        try:
            # Parse and validate command
            parts = input_str.strip().split()
            if not parts or parts[0] not in self.ALLOWED_COMMANDS:
                return f"Error: Unsupported git command. Allowed: {', '.join(sorted(self.ALLOWED_COMMANDS))}"

            # Build command with list arguments (no shell=True)
            cmd = ["git", "-C", self.repo_path] + parts

            # Execute with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return f"Error: {result.stderr.strip() or 'Git command failed'}"

            # Truncate large outputs (diffs can be huge)
            output = result.stdout
            if len(output.splitlines()) > 500:
                lines = output.splitlines()
                output = "\n".join(lines[:500])
                output += f"\n\n(... {len(lines) - 500} more lines truncated)"
                output += "\nTip: Use 'git diff <file>' for specific files or 'git diff --stat' for overview."

            return output

        except FileNotFoundError:
            return "Error: Not a git repository or git is not installed."
        except subprocess.TimeoutExpired:
            return "Error: Git command timed out."
        except Exception as e:
            return f"Error: {str(e)}"
