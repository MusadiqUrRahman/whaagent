"""Tests for graph helper functions: _sanitize_ai_content, _flatten_tool_content,
_make_flat_tool, _format_for_whatsapp, _direct_tool_call, and _is_transient_error."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from whaagent.graph import (
    AgentState,
    agent_node,
)


class TestSanitizeToolArtifacts:
    """Tests for _sanitize_ai_content stripping XML pseudo-tool-calls."""

    def test_strips_web_search_tag(self) -> None:
        from whaagent.graph import _sanitize_ai_content

        raw = 'I will search for that.\n\n<web_search query="site:g1.globo.com top news headlines" />'
        cleaned = _sanitize_ai_content(raw)
        assert cleaned == "I will search for that."
        assert "<web_search" not in cleaned

    def test_strips_tool_call_block(self) -> None:
        from whaagent.graph import _sanitize_ai_content

        raw = 'Let me look that up.\n<tool_call name="web_search">query: news</tool_call'
        cleaned = _sanitize_ai_content(raw)
        assert "<tool_call" not in cleaned
        assert "Let me look that up." in cleaned

    def test_no_artifact_passes_through(self) -> None:
        from whaagent.graph import _sanitize_ai_content

        raw = "Here is your answer. The weather is sunny."
        assert _sanitize_ai_content(raw) == raw

    def test_strips_execute_tag(self) -> None:
        from whaagent.graph import _sanitize_ai_content

        raw = 'Searching now...\n<execute tool="web_fetch" url="https://example.com" />'
        cleaned = _sanitize_ai_content(raw)
        assert "<execute" not in cleaned
        assert "Searching now..." in cleaned

    @pytest.mark.asyncio
    async def test_agent_sanitizes_artifact_from_sub_agent(self) -> None:
        """Agent should strip XML tool artifacts from sub-agent AIMessage."""

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="done"))

        sub_result_msg = AIMessage(content='I will search.\n\n<web_search query="test query" />')
        mock_sub_agent = MagicMock()
        mock_sub_agent.ainvoke = AsyncMock(return_value={"messages": [sub_result_msg]})

        import whaagent.graph as graph_mod

        original_create = graph_mod.create_agent
        graph_mod.create_agent = MagicMock(return_value=mock_sub_agent)
        try:
            state: AgentState = {
                "messages": [HumanMessage(content="search for test")],
                "intent": "tool_use",
                "tool_plan": "web_search",
                "progress": [],
                "final_response": None,
            }
            result = await agent_node(
                state,
                MagicMock(),
                model=mock_model,
                tools=[],
                system_prompt="test",
            )
            returned_msg = result["messages"][0]
            assert isinstance(returned_msg, AIMessage)
            assert "<web_search" not in str(returned_msg.content)
            assert "I will search." in str(returned_msg.content)
        finally:
            graph_mod.create_agent = original_create


class TestFlattenToolContent:
    """Tests for _flatten_tool_content — the fix for MCP structured content.

    MCP tools return [{"type": "text", "text": "..."}] content blocks.
    GLM-5.1 sees these dict wrappers as opaque and responds "can't access results".
    _flatten_tool_content must extract the plain text so the LLM can use it.
    """

    def test_single_text_block(self) -> None:
        from whaagent.graph import _flatten_tool_content

        mcp_content = [{"type": "text", "text": "Globo news headline: Brazil wins Copa America"}]
        result = _flatten_tool_content(mcp_content)
        assert result == "Globo news headline: Brazil wins Copa America"
        # Must NOT contain dict wrappers
        assert '{"type"' not in result
        assert "'type'" not in result

    def test_multiple_text_blocks(self) -> None:
        from whaagent.graph import _flatten_tool_content

        mcp_content = [
            {"type": "text", "text": "Headline 1: Rain expected"},
            {"type": "text", "text": "Headline 2: Markets rally"},
        ]
        result = _flatten_tool_content(mcp_content)
        assert "Headline 1: Rain expected" in result
        assert "Headline 2: Markets rally" in result
        assert "\n" in result  # joined by newline

    def test_mixed_blocks_extracts_only_text(self) -> None:
        from whaagent.graph import _flatten_tool_content

        mcp_content = [
            {"type": "text", "text": "Search result data"},
            {"type": "image", "url": "https://example.com/img.png"},
        ]
        result = _flatten_tool_content(mcp_content)
        assert result == "Search result data"

    def test_plain_string_passes_through(self) -> None:
        from whaagent.graph import _flatten_tool_content

        assert _flatten_tool_content("simple string") == "simple string"

    def test_empty_list_returns_string_repr(self) -> None:
        from whaagent.graph import _flatten_tool_content

        result = _flatten_tool_content([])
        assert isinstance(result, str)

    def test_string_elements_in_list(self) -> None:
        from whaagent.graph import _flatten_tool_content

        result = _flatten_tool_content(["line one", "line two"])
        assert result == "line one\nline two"

    def test_real_mcp_web_search_response(self) -> None:
        """Simulate actual MCP web_search response structure."""
        from whaagent.graph import _flatten_tool_content

        mcp_content = [
            {
                "type": "text",
                "text": "## Search Results\n1. Globo - Top News\n2. BBC - World Update\n3. CNN - Breaking Story",
            }
        ]
        result = _flatten_tool_content(mcp_content)
        assert "Globo - Top News" in result
        assert "## Search Results" in result
        assert isinstance(result, str)
        # CRITICAL: no dict wrappers visible — GLM-5.1 must see plain text
        assert "type" not in result[:20]  # "type" key must not appear at start


class TestMakeFlatTool:
    """Tests for _make_flat_tool — wraps MCP tools to return plain strings.

    Verifies the wrapper correctly flattens structured MCP content so that
    when the sub-agent calls a tool, it receives a plain string ToolMessage
    instead of [{"type": "text", "text": "..."}].
    """

    def _make_mcp_tool(self, name: str, return_value: Any) -> MagicMock:
        """Create a mock MCP tool that returns structured content."""
        from pydantic import BaseModel

        class FakeInput(BaseModel):
            query: str

        tool = MagicMock(spec=["name", "description", "ainvoke", "args_schema"])
        tool.name = name
        tool.description = f"Mock {name} tool"
        tool.args_schema = FakeInput
        tool.ainvoke = AsyncMock(return_value=return_value)
        return tool

    @pytest.mark.asyncio
    async def test_wraps_mcp_tool_flattens_content(self) -> None:
        """Wrapped tool should return plain string, not structured blocks."""
        from whaagent.graph import _make_flat_tool

        mcp_tool = self._make_mcp_tool(
            "web_search",
            [{"type": "text", "text": "Breaking: Earthquake hits Tokyo"}],
        )

        flat_tool = _make_flat_tool(mcp_tool)
        result = await flat_tool.ainvoke({"query": "tokyo earthquake"})

        assert isinstance(result, str)
        assert "Breaking: Earthquake hits Tokyo" in result
        assert '{"type"' not in result

    @pytest.mark.asyncio
    async def test_wrapped_tool_preserves_name_and_description(self) -> None:
        """Wrapped tool must keep same name and description."""
        from whaagent.graph import _make_flat_tool

        mcp_tool = self._make_mcp_tool("web_fetch", [{"type": "text", "text": "page content"}])
        flat_tool = _make_flat_tool(mcp_tool)

        assert flat_tool.name == "web_fetch"
        assert flat_tool.description == "Mock web_fetch tool"

    def test_skips_mock_tools_without_schema(self) -> None:
        """Tools without args_schema should pass through unchanged."""
        from whaagent.graph import _make_flat_tool

        bare_tool = MagicMock(spec=["name"])
        bare_tool.name = "fake"
        # No args_schema attribute

        result = _make_flat_tool(bare_tool)
        assert result is bare_tool

    @pytest.mark.asyncio
    async def test_agent_flattens_tools_via_direct_tool_call(self) -> None:
        """Agent node should flatten MCP tools in the direct tool call path.

        With direct tool execution for tool_use, _direct_tool_call wraps the
        tool via _make_flat_tool, so structured MCP content is flattened to
        plain strings before being sent to the formatting LLM.
        """
        from pydantic import BaseModel

        from whaagent.graph import agent_node

        class SearchInput(BaseModel):
            query: str

        # Create an MCP tool that returns structured content
        mcp_tool = MagicMock(spec=["name", "description", "ainvoke", "args_schema"])
        mcp_tool.name = "web_search"
        mcp_tool.description = "Search the web"
        mcp_tool.args_schema = SearchInput
        # This is what MCP returns — structured blocks
        mcp_tool.ainvoke = AsyncMock(return_value=[{"type": "text", "text": "## Results\n1. Globo news\n2. BBC world"}])

        # Capture what the formatting LLM receives
        llm_calls: list[list[BaseMessage]] = []

        async def capture_llm(messages: list[BaseMessage]) -> AIMessage:
            llm_calls.append(messages)
            return AIMessage(content="Here are the news results.")

        mock_model = AsyncMock()
        mock_model.ainvoke = capture_llm

        state: AgentState = {
            "messages": [HumanMessage(content="What's the news?")],
            "intent": "tool_use",
            "tool_plan": "web_search",
            "progress": [],
            "final_response": None,
        }
        result = await agent_node(
            state,
            MagicMock(),
            model=mock_model,
            tools=[mcp_tool],
            system_prompt="test",
        )

        # Tool should have been called directly
        mcp_tool.ainvoke.assert_called_once()
        # Result should have a final response
        assert result["final_response"] is not None

        # The formatting LLM should have received the flattened plain text,
        # not structured dict wrappers
        assert len(llm_calls) == 1
        llm_input = str(llm_calls[0])
        assert "Globo news" in llm_input
        # Should NOT contain the raw dict structure
        assert '{"type": "text", "text":' not in llm_input

    @pytest.mark.asyncio
    async def test_tool_use_intent_calls_only_selected_tool(self) -> None:
        """For tool_use intent, only the router-selected tool should be called.

        With direct tool execution, web_search is called directly. Other tools
        (web_fetch, curl_fetch) should NOT be invoked.
        """
        from pydantic import BaseModel

        from whaagent.graph import agent_node

        class FakeInput(BaseModel):
            query: str

        def make_tool(name: str) -> MagicMock:
            t = MagicMock(spec=["name", "description", "ainvoke", "args_schema"])
            t.name = name
            t.description = f"Mock {name}"
            t.args_schema = FakeInput
            t.ainvoke = AsyncMock(return_value=[{"type": "text", "text": f"{name} result"}])
            return t

        all_tools = [make_tool("web_search"), make_tool("web_fetch"), make_tool("curl_fetch")]

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Results here"))

        state: AgentState = {
            "messages": [HumanMessage(content="What's the news?")],
            "intent": "tool_use",
            "tool_plan": "web_search",
            "progress": [],
            "final_response": None,
        }
        await agent_node(
            state,
            MagicMock(),
            model=mock_model,
            tools=all_tools,
            system_prompt="test",
        )

        # Only web_search should have been called directly
        all_tools[0].ainvoke.assert_called_once()
        # web_fetch and curl_fetch should NOT have been called
        all_tools[1].ainvoke.assert_not_called()
        all_tools[2].ainvoke.assert_not_called()


class TestFormatForWhatsApp:
    """Tests for template-based WhatsApp formatting (replaces responder LLM)."""

    def test_truncates_to_4096_chars(self) -> None:
        from whaagent.graph import _format_for_whatsapp

        long_text = "A" * 10_000
        result = _format_for_whatsapp(long_text)
        assert len(result) <= 4096
        assert result.endswith("...")

    def test_strips_xml_tool_artifacts(self) -> None:
        from whaagent.graph import _format_for_whatsapp

        text = 'Here is the result.\n<web_search query="barcelona"/>'
        result = _format_for_whatsapp(text)
        assert "<web_search" not in result
        assert "Here is the result." in result

    def test_does_not_strip_inline_json(self) -> None:
        """After removing _JSON_BLOCK_RE, inline JSON should be preserved."""
        from whaagent.graph import _format_for_whatsapp

        text = 'The score is 2-1.\n{"type": "text", "text": "extra data"}'
        result = _format_for_whatsapp(text)
        assert "The score is 2-1." in result

    def test_passes_short_text_unchanged(self) -> None:
        from whaagent.graph import _format_for_whatsapp

        text = "Hello! The weather is nice today."
        result = _format_for_whatsapp(text)
        assert result == text

    def test_handles_empty_string(self) -> None:
        from whaagent.graph import _format_for_whatsapp

        assert _format_for_whatsapp("") == ""


class TestToolRetry:
    """Tests for transient error retry in direct tool calls."""

    def test_is_transient_error_classification(self):
        from whaagent.graph import _is_transient_error

        assert _is_transient_error(ConnectionError("reset")) is True
        assert _is_transient_error(TimeoutError("timed out")) is True
        assert _is_transient_error(OSError("broken pipe")) is True
        assert _is_transient_error(ValueError("invalid input")) is False
        assert _is_transient_error(Exception("503 Service Unavailable")) is True
        assert _is_transient_error(Exception("connection reset by peer")) is True
        assert _is_transient_error(Exception("no active connection")) is True
        assert _is_transient_error(Exception("404 Not Found")) is False

    @pytest.mark.asyncio
    async def test_retry_on_transient_fast_error(self):
        """Should retry once on transient errors if first attempt was fast."""
        from whaagent.graph import _direct_tool_call

        call_count = 0

        class FakeTool:
            name = "web_search"
            description = "Search"
            args_schema = MagicMock()

            async def ainvoke(self, args):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ConnectionError("connection reset")
                return "search results"

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Results here."))

        fake = FakeTool()
        with patch("whaagent.graph._make_flat_tool", return_value=fake):
            result = await _direct_tool_call(
                user_message="test",
                tool_plan="web_search",
                tools=[fake],
                model=mock_model,
                system_prompt="test",
            )

        assert call_count == 2
        assert "Error" not in str(result.content)

    @pytest.mark.asyncio
    async def test_no_retry_on_non_transient_error(self):
        """Should NOT retry on non-transient errors."""
        from whaagent.graph import _direct_tool_call

        call_count = 0

        class FakeTool:
            name = "web_search"
            description = "Search"
            args_schema = MagicMock()

            async def ainvoke(self, args):
                nonlocal call_count
                call_count += 1
                raise ValueError("invalid input")

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Error."))

        fake = FakeTool()
        with patch("whaagent.graph._make_flat_tool", return_value=fake):
            result = await _direct_tool_call(
                user_message="test",
                tool_plan="web_search",
                tools=[fake],
                model=mock_model,
                system_prompt="test",
            )

        assert call_count == 1
        assert "Error" in str(result.content)
