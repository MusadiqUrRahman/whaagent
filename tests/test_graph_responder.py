"""Tests for the Agent/Responder node — tool filtering, middleware, message isolation, and delegation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from whaagent.graph import (
    AgentState,
    agent_node,
)


class TestFilterTools:
    """Tests for _filter_tools function."""

    def _make_tool(self, name: str) -> MagicMock:
        """Create a mock tool with a .name attribute."""
        tool = MagicMock()
        tool.name = name
        return tool

    def test_tool_use_returns_web_and_document_tools(self) -> None:
        """tool_use intent should return web tools (no invoke_agent, no curl_fetch)."""
        from whaagent.graph import _filter_tools

        all_tools = [
            self._make_tool("web_search"),
            self._make_tool("web_fetch"),
            self._make_tool("curl_fetch"),
            self._make_tool("run_shell"),
            self._make_tool("ffmpeg_convert"),
            self._make_tool("invoke_agent"),
        ]
        result = _filter_tools(all_tools, "tool_use")
        names = {t.name for t in result}
        assert names == {"web_search", "web_fetch"}

    def test_research_adds_hackernews_tools(self) -> None:
        """research intent should include hacker_news tools (no invoke_agent)."""
        from whaagent.graph import _filter_tools

        all_tools = [
            self._make_tool("web_search"),
            self._make_tool("hacker_news_top"),
            self._make_tool("hacker_news_item"),
            self._make_tool("run_shell"),
            self._make_tool("invoke_agent"),
        ]
        result = _filter_tools(all_tools, "research")
        names = {t.name for t in result}
        assert names == {"web_search", "hacker_news_top", "hacker_news_item"}

    def test_delegate_returns_only_invoke_agent(self) -> None:
        """delegate intent should return only invoke_agent."""
        from whaagent.graph import _filter_tools

        all_tools = [
            self._make_tool("web_search"),
            self._make_tool("invoke_agent"),
            self._make_tool("run_shell"),
        ]
        result = _filter_tools(all_tools, "delegate")
        names = {t.name for t in result}
        assert names == {"invoke_agent"}

    def test_chat_returns_no_tools(self) -> None:
        """chat intent should return no tools."""
        from whaagent.graph import _filter_tools

        all_tools = [self._make_tool("web_search")]
        result = _filter_tools(all_tools, "chat")
        assert result == []

    def test_unknown_intent_returns_all_tools(self) -> None:
        """Unknown intent should fall back to returning all tools."""
        from whaagent.graph import _filter_tools

        all_tools = [self._make_tool("web_search"), self._make_tool("run_shell")]
        result = _filter_tools(all_tools, "unknown_intent")
        assert result == all_tools


class TestDirectToolExecution:
    """Tests for direct tool call path (bypassing sub-agent)."""

    def _make_tool(self, name: str) -> MagicMock:
        tool = MagicMock(spec=["name", "description", "ainvoke", "args_schema"])
        tool.name = name
        tool.description = f"Mock {name}"
        tool.ainvoke = AsyncMock(return_value="tool result data")
        schema = MagicMock()
        schema.model_json_schema.return_value = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
        tool.args_schema = schema
        return tool

    @pytest.mark.asyncio
    async def test_tool_use_calls_tool_directly(self) -> None:
        """tool_use intent should call the tool directly, not via sub-agent."""

        web_search = self._make_tool("web_search")
        web_search.ainvoke = AsyncMock(return_value="Search results here")

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Here are the search results for your query."))

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
            tools=[web_search],
            system_prompt="You are a helpful assistant.",
        )

        # Tool was called directly (not via sub-agent)
        web_search.ainvoke.assert_called_once()
        # A response was produced
        assert result["final_response"] is not None
        assert len(result["final_response"]) > 0

    @pytest.mark.asyncio
    async def test_tool_use_web_fetch_extracts_url(self) -> None:
        """Direct tool path should extract URL from message for web_fetch."""
        from whaagent.graph import _extract_tool_args

        args = _extract_tool_args("web_fetch", "Read this: https://example.com/article.")
        assert args == {"url": "https://example.com/article"}

    @pytest.mark.asyncio
    async def test_tool_use_web_search_passes_query(self) -> None:
        """Direct tool path should pass user message as query for web_search."""
        from whaagent.graph import _extract_tool_args

        args = _extract_tool_args("web_search", "What's the latest news from Brazil?")
        assert args == {"query": "What's the latest news from Brazil?"}


class TestAgentState:
    """Tests for AgentState TypedDict."""

    def test_state_has_required_fields(self) -> None:
        state: AgentState = {
            "messages": [],
            "intent": "chat",
            "tool_plan": None,
            "progress": [],
            "final_response": None,
        }
        assert state["intent"] == "chat"
        assert state["tool_plan"] is None

    def test_state_accepts_context_field(self) -> None:
        """AgentState should accept an optional context dict."""
        state: AgentState = {
            "messages": [],
            "intent": "chat",
            "tool_plan": None,
            "progress": [],
            "final_response": None,
            "context": {"running_summary": "User asked about F1.", "summary_updated_at": 1712900000.0},
        }
        assert state["context"]["running_summary"] == "User asked about F1."


class TestAgentMiddleware:
    """Tests for agent sub-agent middleware configuration."""

    @pytest.mark.asyncio
    async def test_agent_uses_tool_call_limit(self) -> None:
        """Agent should create sub-agent with ToolCallLimitMiddleware."""
        from unittest.mock import patch

        from langchain.agents.middleware.tool_call_limit import ToolCallLimitMiddleware

        with patch("whaagent.graph.create_agent") as mock_create:
            mock_create.return_value = MagicMock()
            mock_create.return_value.ainvoke = AsyncMock(return_value={"messages": [MagicMock(content="done")]})

            from whaagent.graph import agent_node

            state: AgentState = {
                "messages": [HumanMessage(content="test")],
                "intent": "tool_use",
                "tool_plan": "web_search",
                "progress": [],
                "final_response": None,
            }
            config = MagicMock()

            mock_model = AsyncMock()
            await agent_node(
                state,
                config,
                model=mock_model,
                tools=[],
                system_prompt="test",
            )

            # Verify middleware was passed
            call_kwargs = mock_create.call_args[1] if mock_create.call_args else {}
            middleware_list = call_kwargs.get("middleware", [])
            assert any(isinstance(m, ToolCallLimitMiddleware) for m in middleware_list), (
                f"Expected ToolCallLimitMiddleware in middleware list, got: {middleware_list}"
            )


class TestAgentMessageIsolation:
    """Tests that agent receives a context window for tool_use, not full history."""

    @pytest.mark.asyncio
    async def test_agent_receives_context_window_for_tool_use(self) -> None:
        """tool_use intent should send recent messages (up to 4) for follow-up context."""
        from unittest.mock import patch

        with patch("whaagent.graph.create_agent") as mock_create:
            mock_create.return_value = MagicMock()
            mock_create.return_value.ainvoke = AsyncMock(return_value={"messages": [MagicMock(content="done")]})

            from whaagent.graph import agent_node

            # Simulate accumulated history with previous failures
            state: AgentState = {
                "messages": [
                    HumanMessage(content="What's the weather?"),
                    AIMessage(content="All tools are down"),
                    HumanMessage(content="What are the top news in g1.globo.com?"),
                ],
                "intent": "tool_use",
                "tool_plan": "web_search",
                "progress": [],
                "final_response": None,
            }
            config = MagicMock()

            await agent_node(
                state,
                config,
                model=AsyncMock(),
                tools=[],
                system_prompt="test",
            )

            # Verify recent messages were sent (not full history, not single message)
            invoke_args = mock_create.return_value.ainvoke.call_args
            messages = invoke_args[0][0]["messages"] if invoke_args else []
            # Should include the last HumanMessage at minimum
            human_msgs = [m for m in messages if isinstance(m, HumanMessage)]
            assert len(human_msgs) >= 1, (
                f"Expected at least 1 HumanMessage, got {len(human_msgs)}: {[m.content for m in human_msgs]}"
            )
            # Last HumanMessage must be the current query (with injected date prefix)
            assert human_msgs[-1].content.endswith("What are the top news in g1.globo.com?"), (
                f"Expected message to end with query, got: {human_msgs[-1].content}"
            )


class TestCreateAssistantGraph:
    """Tests for the full graph compilation."""

    def test_graph_compiles(self) -> None:
        from whaagent.graph import create_assistant_graph

        mock_model = MagicMock()
        graph = create_assistant_graph(
            model=mock_model,
            tools=[],
            system_prompt="You are a test assistant.",
        )
        assert graph is not None
        assert hasattr(graph, "ainvoke")


class TestPerNodeModels:
    """Tests for per-node model overrides in create_assistant_graph."""

    @pytest.mark.asyncio
    async def test_router_uses_override_model(self) -> None:
        """Router should use router_model when provided."""
        from whaagent.graph import create_assistant_graph

        primary_model = AsyncMock()
        primary_model.ainvoke = AsyncMock(return_value=AIMessage(content="Hello!"))
        router_model = AsyncMock()

        # Track which model is called for routing
        router_model.ainvoke = AsyncMock(
            return_value=AIMessage(content='{"intent": "chat", "tool_plan": null, "skip_tools": true}')
        )

        graph = create_assistant_graph(
            model=primary_model,
            tools=[],
            system_prompt="You are a test assistant.",
            router_model=router_model,
        )

        await graph.ainvoke(
            {"messages": [HumanMessage(content="Explain recursion in programming")]},
            config={"configurable": {"thread_id": "test-router-override"}},
        )

        # Router should have used router_model
        router_model.ainvoke.assert_called_once()
        # Primary model is used by agent node for chat response
        primary_model.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_overrides_uses_primary_for_all(self) -> None:
        """Without overrides, all nodes should use the primary model."""
        from whaagent.graph import create_assistant_graph

        primary_model = AsyncMock()
        primary_model.ainvoke = AsyncMock(
            side_effect=[
                AIMessage(content='{"intent": "chat", "tool_plan": null, "skip_tools": true}'),
                AIMessage(content="Hello!"),
            ]
        )

        graph = create_assistant_graph(
            model=primary_model,
            tools=[],
            system_prompt="You are a test assistant.",
        )

        await graph.ainvoke(
            {"messages": [HumanMessage(content="What is the meaning of life?")]},
            config={"configurable": {"thread_id": "test-no-overrides"}},
        )

        # Chat goes router → agent: 2 calls (router + agent)
        assert primary_model.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_agent_uses_override_model_for_tool_use(self) -> None:
        """Agent should use agent_model when provided for tool_use intent."""
        from unittest.mock import patch

        from whaagent.graph import create_assistant_graph

        primary_model = AsyncMock()
        agent_model = AsyncMock()

        primary_model.ainvoke = AsyncMock(
            side_effect=[
                AIMessage(content='{"intent": "tool_use", "tool_plan": "web_search", "skip_tools": false}'),
                AIMessage(content="Formatted"),
            ]
        )
        agent_model.ainvoke = AsyncMock(return_value=AIMessage(content="done"))

        with patch("whaagent.graph.create_agent") as mock_create:
            mock_sub_agent = MagicMock()
            mock_sub_agent.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="Search results")]})
            mock_create.return_value = mock_sub_agent

            graph = create_assistant_graph(
                model=primary_model,
                tools=[MagicMock(name="web_search")],
                system_prompt="You are a test assistant.",
                agent_model=agent_model,
            )

            await graph.ainvoke(
                {"messages": [HumanMessage(content="Search for news")]},
                config={"configurable": {"thread_id": "test-agent-override-tool-use"}},
            )

        # Verify agent_model was passed to create_agent, not primary_model
        call_kwargs = mock_create.call_args[1] if mock_create.call_args else {}
        assert call_kwargs.get("model") is agent_model, (
            f"Expected agent_model passed to create_agent, got {call_kwargs.get('model')}"
        )


class TestDelegationFastPath:
    """Tests for direct agent delegation (bypassing thread-based invocation)."""

    @pytest.mark.asyncio
    async def test_delegate_calls_agent_directly(self):
        """delegate intent should call the target agent directly."""

        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(return_value="YouTube transcript result")
        mock_agent_instance._ensure_initialized = AsyncMock()
        mock_cls = MagicMock(return_value=mock_agent_instance)

        with (
            patch("whaagent.registry.AgentRegistry.get", return_value=mock_cls),
            patch("whaagent.registry.AgentRegistry.get_tool_categories", return_value=None),
            patch("whaagent.tools.agent_invocation.DELEGATABLE_AGENTS", ["youtube"]),
        ):
            state: AgentState = {
                "messages": [HumanMessage(content="Analyze https://youtube.com/watch?v=123")],
                "intent": "delegate",
                "tool_plan": "youtube",
                "progress": [],
                "final_response": None,
            }

            result = await agent_node(
                state,
                MagicMock(),
                model=MagicMock(),
                tools=[],
                system_prompt="You are a helpful assistant.",
            )

        assert result["final_response"] is not None
        mock_agent_instance.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_delegate_timeout_returns_error(self):
        """delegate should return error on timeout."""
        import asyncio as _asyncio

        mock_agent_instance = MagicMock()

        async def _slow_run(msg):
            await _asyncio.sleep(200)
            return "never"

        mock_agent_instance.run = _slow_run
        mock_agent_instance._ensure_initialized = AsyncMock()
        mock_cls = MagicMock(return_value=mock_agent_instance)

        with (
            patch("whaagent.registry.AgentRegistry.get", return_value=mock_cls),
            patch("whaagent.registry.AgentRegistry.get_tool_categories", return_value=None),
            patch("whaagent.tools.agent_invocation.DELEGATABLE_AGENTS", ["youtube"]),
        ):
            state: AgentState = {
                "messages": [HumanMessage(content="Analyze YouTube video")],
                "intent": "delegate",
                "tool_plan": "youtube",
                "progress": [],
                "final_response": None,
            }

            result = await agent_node(
                state,
                MagicMock(),
                model=MagicMock(),
                tools=[],
                system_prompt="You are a helpful assistant.",
            )

        assert "timed out" in result["final_response"].lower()
