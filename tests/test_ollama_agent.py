"""Tests for OllamaAgent."""

from whaagent.agents.ollama import OllamaAgent
from whaagent.registry import AgentRegistry


class TestOllamaAgent:
    """Tests for OllamaAgent configuration and behavior."""

    def test_agent_is_registered(self):
        """OllamaAgent should be registered in AgentRegistry."""
        agent_cls = AgentRegistry.get("ollama")
        assert agent_cls is OllamaAgent

    def test_system_prompt_loads_ollama_prompt(self):
        """Agent should load ollama.md, not developer.md."""
        agent = OllamaAgent()
        prompt = agent.system_prompt

        # Should contain key identity phrases
        assert "versatile" in prompt.lower()
        assert "delegate" in prompt.lower()

        # Should NOT contain developer-specific content
        assert "Principal Software Engineer" not in prompt

    def test_system_prompt_not_empty(self):
        """System prompt should not be empty."""
        agent = OllamaAgent()
        assert len(agent.system_prompt) > 100

    def test_local_tools_includes_agent_invocation(self):
        """Agent should have AgentInvocationTool."""
        agent = OllamaAgent()
        tools = agent.local_tools()

        tool_names = [t.name for t in tools]
        assert "invoke_agent" in tool_names

    def test_mcp_servers_configured(self):
        """Agent should have correct MCP servers configured."""
        mcp_servers = AgentRegistry.get_mcp_servers("ollama")
        assert mcp_servers is not None
        assert "toolbox" in mcp_servers

    def test_mcp_servers_excludes_kiwi(self):
        """Agent should NOT have kiwi-com-flight-search (too niche)."""
        mcp_servers = AgentRegistry.get_mcp_servers("ollama")
        assert "kiwi-com-flight-search" not in mcp_servers

    def test_regression_wrong_prompt(self):
        """Regression test: ensure we never use developer prompt again."""
        agent = OllamaAgent()
        prompt = agent.system_prompt

        # These phrases should NOT appear (they're from developer prompt)
        forbidden_phrases = [
            "Principal Software Engineer",
            "MANDATORY FILE EDITING WORKFLOW",
            "edit_file",
            "read_file_fragment",
            "find_files",
        ]

        for phrase in forbidden_phrases:
            assert phrase not in prompt, f"Found forbidden phrase '{phrase}' in ollama prompt"
