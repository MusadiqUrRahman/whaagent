"""Tests for GitCommandTool."""

import subprocess

from whaagent.tools.git_command import GitCommandTool


class TestGitCommandTool:
    """Tests for GitCommandTool."""

    def test_tool_has_correct_name(self):
        """Tool should have name 'git_command'."""
        tool = GitCommandTool()
        assert tool.name == "git_command"

    def test_tool_has_description(self):
        """Tool should have a description."""
        tool = GitCommandTool()
        assert len(tool.description) > 0

    def test_default_repo_path_is_cwd(self):
        """Default repo_path should be current directory."""
        tool = GitCommandTool()
        from pathlib import Path

        assert tool.repo_path == str(Path.cwd())

    def test_custom_repo_path(self):
        """Should accept custom repo_path."""
        tool = GitCommandTool(repo_path="/custom/path")
        assert tool.repo_path == "/custom/path"

    def test_invoke_empty_input_returns_error(self):
        """Empty input should return error."""
        tool = GitCommandTool()
        result = tool.invoke("")
        assert "Error: Unsupported git command" in result

    def test_invoke_unsupported_command_returns_error(self):
        """Unsupported commands should be rejected."""
        tool = GitCommandTool()
        result = tool.invoke("push origin main")
        assert "Error: Unsupported git command" in result
        assert "push" not in result

    def test_status_command_executes(self, monkeypatch):
        """git status should execute successfully."""

        class MockResult:
            returncode = 0
            stdout = "On branch main\nnothing to commit"
            stderr = ""

        def mock_run(*args, **kwargs):
            return MockResult()

        monkeypatch.setattr("subprocess.run", mock_run)

        tool = GitCommandTool()
        result = tool.invoke("status")
        assert "On branch main" in result
        assert "nothing to commit" in result

    def test_git_error_returns_error_message(self, monkeypatch):
        """Git errors should be returned as error messages."""

        class MockResult:
            returncode = 1
            stdout = ""
            stderr = "fatal: not a git repository"

        def mock_run(*args, **kwargs):
            return MockResult()

        monkeypatch.setattr("subprocess.run", mock_run)

        tool = GitCommandTool()
        result = tool.invoke("status")
        assert result.startswith("Error:")
        assert "not a git repository" in result

    def test_timeout_handling(self, monkeypatch):
        """Command timeout should return timeout error."""

        def mock_run(*args, **kwargs):
            raise subprocess.TimeoutExpired("git", 30)

        monkeypatch.setattr("subprocess.run", mock_run)

        tool = GitCommandTool()
        result = tool.invoke("status")
        assert "Error: Git command timed out" in result

    def test_large_output_truncated(self, monkeypatch):
        """Large outputs should be truncated after 500 lines."""

        class MockResult:
            returncode = 0
            stdout = "\n".join([f"Line {i}" for i in range(600)])
            stderr = ""

        def mock_run(*args, **kwargs):
            return MockResult()

        monkeypatch.setattr("subprocess.run", mock_run)

        tool = GitCommandTool()
        result = tool.invoke("log")
        assert "100 more lines truncated" in result
        assert "git diff <file>" in result
