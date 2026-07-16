# tests/test_agent_invocation.py
"""Tests for AgentInvocationTool."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from whaagent.tools.agent_invocation import AgentInvocationTool


class TestAgentInvocationTool:
    """Tests for AgentInvocationTool."""

    def test_tool_name(self):
        """Tool should have correct name."""
        tool = AgentInvocationTool()
        assert tool.name == "invoke_agent"

    def test_tool_description_not_empty(self):
        """Tool should have a description."""
        tool = AgentInvocationTool()
        assert len(tool.description) > 50
        assert "agent" in tool.description.lower()

    def test_invoke_valid_agent_returns_response(self):
        """Valid agent invocation should return response."""
        tool = AgentInvocationTool()

        input_json = json.dumps({"agent_name": "developer", "prompt": "Test prompt"})

        with patch("whaagent.tools.agent_invocation.AgentRegistry") as mock_registry:
            mock_agent_cls = MagicMock()
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value="Agent response")
            mock_agent_cls.return_value = mock_agent
            mock_registry.get.return_value = mock_agent_cls
            mock_registry.list_agents.return_value = ["developer", "learning", "news", "youtube"]

            result = tool.invoke(input_json)
            assert result == "Agent response"

    def test_invoke_agent_not_found_returns_error(self):
        """Non-existent agent should return error message."""
        tool = AgentInvocationTool()

        input_json = json.dumps({"agent_name": "nonexistent", "prompt": "Test prompt"})

        with patch("whaagent.tools.agent_invocation.AgentRegistry") as mock_registry:
            mock_registry.get.return_value = None
            mock_registry.list_agents.return_value = ["developer", "learning", "news", "youtube"]

            result = tool.invoke(input_json)
            assert "not found" in result.lower()
            assert "developer" in result  # Lists available agents

    def test_invoke_invalid_json_returns_error(self):
        """Invalid JSON input should return clear error."""
        tool = AgentInvocationTool()
        result = tool.invoke("not valid json")
        assert "error" in result.lower()
        assert "json" in result.lower()

    def test_invoke_missing_agent_name_returns_error(self):
        """Missing agent_name field should return error."""
        tool = AgentInvocationTool()
        result = tool.invoke(json.dumps({"prompt": "test"}))
        assert "error" in result.lower()
        assert "agent_name" in result.lower()

    def test_invoke_missing_prompt_returns_error(self):
        """Missing prompt field should return error."""
        tool = AgentInvocationTool()
        result = tool.invoke(json.dumps({"agent_name": "developer"}))
        assert "error" in result.lower()
        assert "prompt" in result.lower()

    def test_invoke_agent_crash_returns_error_not_exception(self):
        """Agent crash should return error string, not raise."""
        tool = AgentInvocationTool()

        input_json = json.dumps({"agent_name": "developer", "prompt": "Test prompt"})

        with patch("whaagent.tools.agent_invocation.AgentRegistry") as mock_registry:
            mock_agent_cls = MagicMock()
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(side_effect=RuntimeError("Agent crashed"))
            mock_agent_cls.return_value = mock_agent
            mock_registry.get.return_value = mock_agent_cls
            mock_registry.list_agents.return_value = ["developer"]

            # Should NOT raise, should return error string
            result = tool.invoke(input_json)
            assert "error" in result.lower()

    def test_invoke_blocks_self_delegation(self):
        """Tool should block ollama from delegating to itself."""
        tool = AgentInvocationTool()

        input_json = json.dumps({"agent_name": "ollama", "prompt": "Test prompt"})

        result = tool.invoke(input_json)
        assert "cannot delegate to itself" in result.lower()

    def test_to_langchain_tool(self):
        """Tool should convert to LangChain StructuredTool."""
        from langchain_core.tools import StructuredTool

        tool = AgentInvocationTool()
        lc_tool = tool.to_langchain_tool()

        assert isinstance(lc_tool, StructuredTool)
        assert lc_tool.name == "invoke_agent"

    def test_invoke_in_async_context_clears_httpx_cache(self):
        """Running in a new loop should clear the langchain httpx LRU cache.

        This verifies the fix for the 'bound to a different event loop' crash.
        """
        from whaagent.tools.agent_invocation import _clear_langchain_httpx_cache

        mock_async_cache = MagicMock()
        mock_sync_cache = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "langchain_openai": MagicMock(),
                "langchain_openai.chat_models": MagicMock(),
                "langchain_openai.chat_models._client_utils": MagicMock(
                    _cached_async_httpx_client=mock_async_cache,
                    _cached_sync_httpx_client=mock_sync_cache,
                ),
            },
        ):
            _clear_langchain_httpx_cache()
            mock_async_cache.cache_clear.assert_called_once()
            mock_sync_cache.cache_clear.assert_called_once()

    def test_clear_httpx_cache_is_safe_without_langchain(self):
        """_clear_langchain_httpx_cache should not crash if langchain is missing."""
        from whaagent.tools.agent_invocation import _clear_langchain_httpx_cache

        with patch.dict("sys.modules", {"langchain_openai.chat_models._client_utils": None}):
            # Should not raise
            _clear_langchain_httpx_cache()

    def test_default_timeout_is_240(self):
        """Default timeout should be 240 seconds."""
        from whaagent.tools.agent_invocation import _DEFAULT_AGENT_TIMEOUT

        assert _DEFAULT_AGENT_TIMEOUT == 240

    def test_env_var_overrides_default_timeout(self):
        """AGENT_INVOCATION_TIMEOUT env var should override default."""
        import importlib

        with patch.dict("os.environ", {"AGENT_INVOCATION_TIMEOUT": "300"}):
            # Reimport to pick up the new env var
            import whaagent.tools.agent_invocation as mod

            importlib.reload(mod)
            assert mod._DEFAULT_AGENT_TIMEOUT == 300

        # Reload again to restore default
        importlib.reload(mod)

    def test_asyncio_run_path_clears_httpx_cache(self):
        """The asyncio.run() fallback path should also clear httpx cache."""
        tool = AgentInvocationTool()

        input_json = json.dumps({"agent_name": "developer", "prompt": "Test prompt"})

        with (
            patch("whaagent.tools.agent_invocation.AgentRegistry") as mock_registry,
            patch("whaagent.tools.agent_invocation._clear_langchain_httpx_cache") as mock_clear,
        ):
            mock_agent_cls = MagicMock()
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value="Agent response")
            mock_agent_cls.return_value = mock_agent
            mock_registry.get.return_value = mock_agent_cls
            mock_registry.list_agents.return_value = ["developer"]
            mock_registry.get_tool_categories.return_value = []

            # Force the asyncio.run() path by making get_running_loop raise RuntimeError
            with patch("asyncio.get_running_loop", side_effect=RuntimeError("no running loop")):
                tool.invoke(input_json)

            # Both paths should clear the cache
            assert mock_clear.called
