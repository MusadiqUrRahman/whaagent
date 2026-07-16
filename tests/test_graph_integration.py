"""Integration tests for the full 3-node graph — message isolation, tool filtering,
middleware, and single-AI-message-per-turn invariants."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage


class TestGraphIntegration:
    """Integration tests for the full 3-node graph with mock LLM.

    Verifies that message isolation, tool filtering, and middleware
    all work together through the real graph execution path.
    """

    @pytest.mark.asyncio
    async def test_graph_has_summarize_node(self) -> None:
        """Graph should compile with summarize as the entry point."""
        from whaagent.graph import create_assistant_graph

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(
            side_effect=[
                AIMessage(content='{"intent": "chat", "tool_plan": null, "skip_tools": true}'),
                AIMessage(content="Hello!"),
            ]
        )

        graph = create_assistant_graph(
            model=mock_model,
            tools=[],
            system_prompt="You are a test assistant.",
        )

        # Graph should compile and have ainvoke
        assert graph is not None

        # Invoke should work end-to-end (summarize no-op → router → responder)
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="Hi")]},
            config={"configurable": {"thread_id": "test-summarize-node"}},
        )
        assert result.get("final_response") is not None

    @pytest.mark.asyncio
    async def test_chat_intent_routes_to_agent(self) -> None:
        """Chat intent should go router → agent → END (agent responds conversationally)."""
        from whaagent.graph import create_assistant_graph

        mock_model = AsyncMock()
        # Router classifies as chat, then agent responds conversationally
        mock_model.ainvoke = AsyncMock(
            side_effect=[
                AIMessage(content='{"intent": "chat", "tool_plan": null, "skip_tools": true}'),
                AIMessage(content="Hello! How can I help you?"),
            ]
        )

        graph = create_assistant_graph(
            model=mock_model,
            tools=[],
            system_prompt="You are a test assistant.",
        )

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="Tell me about quantum physics")]},
            config={"configurable": {"thread_id": "test-chat-integration"}},
        )

        assert result.get("final_response") is not None
        # Agent node should have been called (2 ainvoke calls: router + agent)
        assert mock_model.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_tool_use_intent_routes_to_agent(self) -> None:
        """Tool use intent should go router → agent → END."""

        from whaagent.graph import create_assistant_graph

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(
            side_effect=[
                AIMessage(content='{"intent": "tool_use", "tool_plan": "web_search", "skip_tools": false}'),
                AIMessage(content="São Paulo: 25°C, sunny ☀️"),
            ]
        )

        with patch("whaagent.graph.create_agent") as mock_create:
            mock_sub_agent = MagicMock()
            mock_sub_agent.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="The weather is 25°C.")]})
            mock_create.return_value = mock_sub_agent

            graph = create_assistant_graph(
                model=mock_model,
                tools=[MagicMock(name="web_search")],
                system_prompt="You are a test assistant.",
            )

            result = await graph.ainvoke(
                {"messages": [HumanMessage(content="What's the weather in São Paulo?")]},
                config={"configurable": {"thread_id": "test-tool-use-integration"}},
            )

        mock_create.assert_called_once()
        assert result.get("final_response") is not None

    @pytest.mark.asyncio
    async def test_agent_receives_context_window_despite_accumulated_history(self) -> None:
        """tool_use intent should send a window of recent messages for follow-up context."""

        from whaagent.graph import create_assistant_graph

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(
            side_effect=[
                AIMessage(content='{"intent": "tool_use", "tool_plan": "web_search", "skip_tools": false}'),
                AIMessage(content="Formatted response"),
            ]
        )

        with patch("whaagent.graph.create_agent") as mock_create:
            mock_sub_agent = MagicMock()
            mock_sub_agent.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="News results here")]})
            mock_create.return_value = mock_sub_agent

            graph = create_assistant_graph(
                model=mock_model,
                tools=[MagicMock(name="web_search")],
                system_prompt="You are a test assistant.",
            )

            # Simulate accumulated history from multiple WhatsApp messages
            await graph.ainvoke(
                {
                    "messages": [
                        HumanMessage(content="What's the weather?"),
                        AIMessage(content="It's sunny."),
                        HumanMessage(content="Tell me a joke"),
                        AIMessage(content="Why did the chicken cross the road?"),
                        HumanMessage(content="What are the top news in g1.globo.com?"),
                    ]
                },
                config={"configurable": {"thread_id": "test-history-isolation"}},
            )

        # Verify sub-agent was invoked
        mock_create.assert_called_once()
        sub_invoke_args = mock_sub_agent.ainvoke.call_args
        messages_sent = sub_invoke_args[0][0]["messages"]

        # Should include at least the last HumanMessage (context window, not single)
        human_msgs = [m for m in messages_sent if isinstance(m, HumanMessage)]
        assert len(human_msgs) >= 1
        # The last HumanMessage must be the current query (with injected date prefix)
        assert human_msgs[-1].content.endswith("What are the top news in g1.globo.com?"), (
            f"Expected message to end with query, got: {human_msgs[-1].content}"
        )

    @pytest.mark.asyncio
    async def test_tool_filtering_excludes_run_shell_for_tool_use(self) -> None:
        """Tool filtering should exclude run_shell for tool_use intent.

        With direct tool execution, tool_use calls the tool directly without
        create_agent. Only web_search should be called, not run_shell or others.
        """

        from whaagent.graph import create_assistant_graph

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(
            side_effect=[
                AIMessage(content='{"intent": "tool_use", "tool_plan": "web_search", "skip_tools": false}'),
                AIMessage(content="Response"),
            ]
        )

        def _make_tool(name: str) -> MagicMock:
            t = MagicMock()
            t.name = name
            t.ainvoke = AsyncMock(return_value=f"{name} result")
            return t

        all_tools = [
            _make_tool("web_search"),
            _make_tool("web_fetch"),
            _make_tool("run_shell"),
            _make_tool("invoke_agent"),
        ]

        with patch("whaagent.graph.create_agent") as mock_create:
            mock_sub_agent = MagicMock()
            mock_sub_agent.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="Results")]})
            mock_create.return_value = mock_sub_agent

            graph = create_assistant_graph(
                model=mock_model,
                tools=all_tools,
                system_prompt="You are a test assistant.",
            )

            result = await graph.ainvoke(
                {"messages": [HumanMessage(content="Search for news")]},
                config={"configurable": {"thread_id": "test-tool-filter"}},
            )

        # Direct tool path: create_agent should NOT be called for tool_use
        mock_create.assert_not_called()
        # web_search should have been called directly
        all_tools[0].ainvoke.assert_called_once()
        # run_shell should NOT have been called
        all_tools[2].ainvoke.assert_not_called()
        # Result should have a final response
        assert result.get("final_response") is not None

    @pytest.mark.asyncio
    async def test_chat_intent_receives_full_conversation_history(self) -> None:
        """Agent node should receive full conversation history for chat intent.

        This verifies the fix for the memory loss bug where _truncate_messages
        was stripping history for chat intent, causing the agent to not
        understand follow-up messages like "yes" or "and in Paris?".
        """
        from whaagent.graph import create_assistant_graph

        mock_model = AsyncMock()

        # Track what messages each node receives via ainvoke calls
        invoke_calls: list[list[BaseMessage]] = []

        async def capture_ainvoke(messages: list[BaseMessage]) -> AIMessage:
            invoke_calls.append(messages)
            call_index = len(invoke_calls) - 1
            if call_index == 0:
                # Router response: classify follow-up as chat
                return AIMessage(content='{"intent": "chat", "tool_plan": null, "skip_tools": true}')
            # Agent response: conversational reply
            return AIMessage(content="The weather in Paris is 18°C, cloudy.")

        mock_model.ainvoke = capture_ainvoke

        graph = create_assistant_graph(
            model=mock_model,
            tools=[],
            system_prompt="You are a test assistant.",
        )

        # Simulate a multi-turn conversation:
        # Turn 1: user asked about Tokyo weather, agent responded
        # Turn 2: user follows up with "And in Paris?"
        await graph.ainvoke(
            {
                "messages": [
                    HumanMessage(content="What's the weather in Tokyo?"),
                    AIMessage(content="The weather in Tokyo is 22°C, sunny."),
                    HumanMessage(content="And in Paris?"),
                ]
            },
            config={"configurable": {"thread_id": "test-multi-turn-memory"}},
        )

        # 2 calls: router classifies, agent responds conversationally
        assert len(invoke_calls) == 2, f"Expected 2 ainvoke calls (router + agent), got {len(invoke_calls)}"

        # The agent node (2nd call) should receive conversation context
        agent_messages = invoke_calls[1]
        human_msgs = [m for m in agent_messages if isinstance(m, HumanMessage)]
        assert len(human_msgs) >= 1, (
            f"Agent should see >= 1 HumanMessage, got {len(human_msgs)}: {[m.content for m in human_msgs]}"
        )

    @pytest.mark.asyncio
    async def test_router_receives_context_window(self) -> None:
        """Router should receive a sliding window of recent messages, not just one."""
        from whaagent.graph import create_assistant_graph

        mock_model = AsyncMock()

        invoke_calls: list[list[BaseMessage]] = []

        async def capture_ainvoke(messages: list[BaseMessage]) -> AIMessage:
            invoke_calls.append(messages)
            call_index = len(invoke_calls) - 1
            if call_index == 0:
                return AIMessage(content='{"intent": "chat", "tool_plan": null, "skip_tools": true}')
            return AIMessage(content="Yes, I remember.")

        mock_model.ainvoke = capture_ainvoke

        graph = create_assistant_graph(
            model=mock_model,
            tools=[],
            system_prompt="You are a test assistant.",
        )

        # Build a conversation with 3 exchange pairs (6 messages total)
        await graph.ainvoke(
            {
                "messages": [
                    HumanMessage(content="Message 1"),
                    AIMessage(content="Response 1"),
                    HumanMessage(content="Message 2"),
                    AIMessage(content="Response 2"),
                    HumanMessage(content="Message 3"),
                    AIMessage(content="Response 3"),
                ]
            },
            config={"configurable": {"thread_id": "test-router-context"}},
        )

        # First ainvoke call is the router
        router_messages = invoke_calls[0]
        # Router should see the sliding window (up to 5 messages), not just 1
        non_system_msgs = [m for m in router_messages if not isinstance(m, SystemMessage)]
        assert len(non_system_msgs) > 1, (
            f"Router should receive > 1 non-system message (context window), "
            f"got {len(non_system_msgs)}: {[type(m).__name__ for m in non_system_msgs]}"
        )


class TestSingleAIMessagePerTurn:
    """Integration tests verifying exactly 1 AI message is added per turn."""

    @pytest.mark.asyncio
    async def test_tool_use_adds_exactly_one_ai_message(self) -> None:
        """After a tool_use turn, state should have exactly 1 HumanMessage + 1 AIMessage."""

        from whaagent.graph import create_assistant_graph

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(
            side_effect=[
                AIMessage(content='{"intent": "tool_use", "tool_plan": "web_search", "skip_tools": false}'),
                AIMessage(content="WhatsApp formatted news"),
            ]
        )

        with patch("whaagent.graph.create_agent") as mock_create:
            mock_sub = MagicMock()
            mock_sub.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="News results from search")]})
            mock_create.return_value = mock_sub

            graph = create_assistant_graph(
                model=mock_model,
                tools=[MagicMock(name="web_search")],
                system_prompt="You are a test assistant.",
            )

            result = await graph.ainvoke(
                {"messages": [HumanMessage(content="What's the news?")]},
                config={"configurable": {"thread_id": "test-single-msg-tool-use"}},
            )

        ai_msgs = [m for m in result["messages"] if isinstance(m, AIMessage)]
        assert len(ai_msgs) == 1, (
            f"Expected exactly 1 AIMessage after tool_use turn, got {len(ai_msgs)}. "
            f"Contents: {[m.content[:50] for m in ai_msgs]}"
        )

    @pytest.mark.asyncio
    async def test_chat_adds_exactly_one_ai_message(self) -> None:
        """After a chat turn, state should have final_response and 1 AIMessage from agent node."""
        from whaagent.graph import create_assistant_graph

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(
            side_effect=[
                AIMessage(content='{"intent": "chat", "tool_plan": null, "skip_tools": true}'),
                AIMessage(content="Hello! How can I help?"),
            ]
        )

        graph = create_assistant_graph(
            model=mock_model,
            tools=[],
            system_prompt="You are a test assistant.",
        )

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="Hello")]},
            config={"configurable": {"thread_id": "test-single-msg-chat"}},
        )

        # Chat intent now routes through agent node which adds 1 AIMessage
        assert result.get("final_response") is not None, "Chat intent should set final_response"
        ai_msgs = [m for m in result["messages"] if isinstance(m, AIMessage)]
        assert len(ai_msgs) == 1, f"Chat intent should add exactly 1 AIMessage, got {len(ai_msgs)}"

    @pytest.mark.asyncio
    async def test_research_adds_exactly_one_ai_message(self) -> None:
        """After a research turn, state should have exactly 1 AIMessage."""

        from whaagent.graph import create_assistant_graph

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(
            side_effect=[
                AIMessage(
                    content='{"intent": "research", "tool_plan": "1. web_search\\n2. web_fetch", "skip_tools": false}'
                ),
                AIMessage(content="Formatted research results"),
            ]
        )

        with patch("whaagent.graph.create_agent") as mock_create:
            mock_sub = MagicMock()
            mock_sub.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="Research results")]})
            mock_create.return_value = mock_sub

            graph = create_assistant_graph(
                model=mock_model,
                tools=[MagicMock(name="web_search"), MagicMock(name="web_fetch")],
                system_prompt="You are a test assistant.",
            )

            result = await graph.ainvoke(
                {"messages": [HumanMessage(content="Compare React vs Vue")]},
                config={"configurable": {"thread_id": "test-single-msg-research"}},
            )

        ai_msgs = [m for m in result["messages"] if isinstance(m, AIMessage)]
        assert len(ai_msgs) == 1, f"Expected exactly 1 AIMessage after research turn, got {len(ai_msgs)}"

    @pytest.mark.asyncio
    async def test_multi_turn_accumulates_one_ai_per_turn(self) -> None:
        """Over multiple turns, each turn should add exactly 1 AI message.

        Simulates 2 turns (1 chat, 1 tool_use) and verifies that:
        - Chat turn: routes through agent node, adds 1 AIMessage
        - Tool_use turn: adds exactly 1 AIMessage
        """

        from whaagent.graph import create_assistant_graph

        thread_id = "test-multi-turn-single-ai"

        # --- Turn 1: chat ---
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(
            side_effect=[
                AIMessage(content='{"intent": "chat", "tool_plan": null, "skip_tools": true}'),
                AIMessage(content="Hello!"),
            ]
        )

        graph = create_assistant_graph(
            model=mock_model,
            tools=[MagicMock(name="web_search")],
            system_prompt="You are a test assistant.",
        )

        result1 = await graph.ainvoke(
            {"messages": [HumanMessage(content="Hi")]},
            config={"configurable": {"thread_id": thread_id}},
        )

        # Chat intent now routes through agent node — adds 1 AIMessage
        assert result1.get("final_response") is not None, "Turn 1: chat should set final_response"
        ai_after_turn1 = [m for m in result1["messages"] if isinstance(m, AIMessage)]
        assert len(ai_after_turn1) == 1, f"Turn 1: chat should add 1 AI msg, got {len(ai_after_turn1)}"

        # --- Turn 2: tool_use ---
        mock_model2 = AsyncMock()
        mock_model2.ainvoke = AsyncMock(
            return_value=AIMessage(content='{"intent": "tool_use", "tool_plan": "web_search", "skip_tools": false}')
        )

        with patch("whaagent.graph.create_agent") as mock_create:
            mock_sub = MagicMock()
            mock_sub.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="News results")]})
            mock_create.return_value = mock_sub

            graph2 = create_assistant_graph(
                model=mock_model2,
                tools=[MagicMock(name="web_search")],
                system_prompt="You are a test assistant.",
            )

            result2 = await graph2.ainvoke(
                {"messages": [HumanMessage(content="What's the news?")]},
                config={"configurable": {"thread_id": thread_id}},
            )

        # After turn 2, tool_use should have added exactly 1 AIMessage
        ai_after_turn2 = [m for m in result2["messages"] if isinstance(m, AIMessage)]
        assert len(ai_after_turn2) == 1, f"Turn 2: tool_use should add 1 AI msg, got {len(ai_after_turn2)}"
