"""Tests for CommitterAgent."""

from whaagent.agents.committer import CommitterAgent
from whaagent.registry import AgentRegistry


class TestCommitterAgent:
    """Tests for CommitterAgent."""

    def test_agent_is_registered(self):
        """CommitterAgent should be registered in AgentRegistry."""
        agent_cls = AgentRegistry.get("committer")
        assert agent_cls is CommitterAgent

    def test_system_prompt_loads_committer_prompt(self):
        """Agent should load committer.md prompt."""
        agent = CommitterAgent()
        prompt = agent.system_prompt

        # Should contain committer-specific content
        assert "Committer" in prompt
        assert "conventional commit" in prompt.lower()
        assert "git_command" in prompt

    def test_system_prompt_not_empty(self):
        """System prompt should not be empty."""
        agent = CommitterAgent()
        assert len(agent.system_prompt) > 100

    def test_local_tools_includes_git_command(self):
        """Agent should have GitCommandTool."""
        agent = CommitterAgent()
        tools = agent.local_tools()

        tool_names = [t.name for t in tools]
        assert "git_command" in tool_names

    def test_git_command_tool_has_correct_description(self):
        """GitCommandTool should have git-related description."""
        agent = CommitterAgent()
        tools = agent.local_tools()

        git_tool = next(t for t in tools if t.name == "git_command")
        assert "git" in git_tool.description.lower()
