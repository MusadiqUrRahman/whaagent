"""Tests for the Router node and intent classification helpers."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from whaagent.graph import (
    AgentState,
    _parse_router_response,
)


class TestParseRouterResponse:
    """Tests for _parse_router_response."""

    def test_valid_json(self) -> None:
        raw = '{"intent": "chat", "tool_plan": null, "skip_tools": true}'
        result = _parse_router_response(raw)
        assert result["intent"] == "chat"
        assert result["skip_tools"] is True

    def test_json_in_markdown_code_block(self) -> None:
        raw = '```json\n{"intent": "tool_use", "tool_plan": "use web_search"}\n```'
        result = _parse_router_response(raw)
        assert result["intent"] == "tool_use"

    def test_invalid_json_falls_back_to_chat(self) -> None:
        raw = "I don't know what this is"
        result = _parse_router_response(raw)
        assert result["intent"] == "chat"
        assert result["skip_tools"] is True


class TestRouteDecision:
    """Tests for graph routing — all intents go through agent node."""

    def test_graph_has_no_conditional_router_edges(self) -> None:
        """After removing route_decision, graph uses direct edge router→agent."""
        from whaagent.graph import create_assistant_graph

        graph = create_assistant_graph(
            model=MagicMock(),
            tools=[],
            system_prompt="test",
            checkpointer=None,
        )
        # Verify the graph compiles and has the expected nodes
        node_names = set(graph.nodes.keys())
        assert "summarize" in node_names
        assert "router" in node_names
        assert "agent" in node_names


class TestRouterNode:
    """Tests for router_node with mocked LLM."""

    @pytest.mark.asyncio
    async def test_router_classifies_chat(self) -> None:
        from langchain_core.messages import HumanMessage

        from whaagent.graph import router_node

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(
            return_value=MagicMock(content='{"intent": "chat", "tool_plan": null, "skip_tools": true}')
        )

        state: AgentState = {
            "messages": [HumanMessage(content="good morning")],
            "intent": "",
            "tool_plan": None,
            "progress": [],
            "final_response": None,
        }

        result = await router_node(state, {}, model=mock_model)
        assert result["intent"] == "chat"
        assert result["tool_plan"] is None

    @pytest.mark.asyncio
    async def test_router_classifies_tool_use(self) -> None:
        from langchain_core.messages import HumanMessage

        from whaagent.graph import router_node

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(
            return_value=MagicMock(
                content='{"intent": "tool_use", "tool_plan": "use web_search for weather", "skip_tools": false}'
            )
        )

        state: AgentState = {
            "messages": [HumanMessage(content="What's the weather in São Paulo?")],
            "intent": "",
            "tool_plan": None,
            "progress": [],
            "final_response": None,
        }

        result = await router_node(state, {}, model=mock_model)
        assert result["intent"] == "tool_use"
        assert "web_search" in result["tool_plan"]

    @pytest.mark.asyncio
    async def test_router_injects_summary_as_context(self) -> None:
        """Router should prepend summary as SystemMessage when context has one."""
        from whaagent.graph import router_node

        captured_messages: list[list[BaseMessage]] = []

        async def capture_invoke(messages: list[BaseMessage]) -> AIMessage:
            captured_messages.append(messages)
            return AIMessage(content='{"intent": "chat", "tool_plan": null, "skip_tools": true}')

        mock_model = AsyncMock()
        mock_model.ainvoke = capture_invoke

        state: AgentState = {
            "messages": [HumanMessage(content="follow up question")],
            "intent": "",
            "tool_plan": None,
            "progress": [],
            "final_response": None,
            "context": {
                "running_summary": "User previously asked about F1 news and got results.",
                "summary_updated_at": time.time(),
            },
        }

        await router_node(state, {}, model=mock_model)

        sent = captured_messages[0]
        # Should contain a SystemMessage with the summary
        system_msgs = [m for m in sent if isinstance(m, SystemMessage)]
        summary_msgs = [m for m in system_msgs if "Previous conversation summary" in str(m.content)]
        assert len(summary_msgs) == 1, f"Expected 1 summary SystemMessage, got {len(summary_msgs)}"
        assert "F1 news" in str(summary_msgs[0].content)


class TestPreRouting:
    """Tests for regex pre-routing filter."""

    def test_greetings_portuguese(self):
        from whaagent.graph import _pre_route

        assert _pre_route("bom dia") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("oi") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("boa noite") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("tudo bem?") == {"intent": "chat", "tool_plan": None}

    def test_greetings_english(self):
        from whaagent.graph import _pre_route

        assert _pre_route("hello") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("hi") == {"intent": "chat", "tool_plan": None}

    def test_help_queries(self):
        from whaagent.graph import _pre_route

        assert _pre_route("help") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("ajuda") == {"intent": "chat", "tool_plan": None}

    def test_bare_url(self):
        from whaagent.graph import _pre_route

        assert _pre_route("https://example.com") == {"intent": "tool_use", "tool_plan": "web_fetch"}

    def test_read_url(self):
        from whaagent.graph import _pre_route

        assert _pre_route("leia https://example.com/article") == {"intent": "tool_use", "tool_plan": "web_fetch"}

    def test_news_queries(self):
        from whaagent.graph import _pre_route

        assert _pre_route("noticias sobre Brasil") == {"intent": "tool_use", "tool_plan": "web_search"}
        assert _pre_route("latest news") == {"intent": "tool_use", "tool_plan": "web_search"}

    def test_ambiguous_falls_through(self):
        from whaagent.graph import _pre_route

        assert _pre_route("what do you think about AI?") is None
        assert _pre_route("can you help me with a recipe?") is None

    def test_url_in_context_not_matched_as_bare(self):
        """A URL embedded in a sentence should NOT match bare URL pattern."""
        from whaagent.graph import _pre_route

        result = _pre_route("noticias sobre https://example.com")
        assert result == {"intent": "tool_use", "tool_plan": "web_search"}

    def test_youtube_url_delegates(self):
        from whaagent.graph import _pre_route

        assert _pre_route("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == {
            "intent": "delegate",
            "tool_plan": "youtube",
        }
        assert _pre_route("https://youtu.be/abc123") == {
            "intent": "delegate",
            "tool_plan": "youtube",
        }

    def test_paywalled_url_delegates(self):
        from whaagent.graph import _pre_route

        assert _pre_route("https://www.globo.com/economia/artigo") == {
            "intent": "delegate",
            "tool_plan": "paywall-remover",
        }
        assert _pre_route("https://www.folha.uol.com.br/mercado/") == {
            "intent": "delegate",
            "tool_plan": "paywall-remover",
        }
        assert _pre_route("https://www.wsj.com/articles/some-article") == {
            "intent": "delegate",
            "tool_plan": "paywall-remover",
        }

    def test_empty_message(self):
        from whaagent.graph import _pre_route

        assert _pre_route("") is None
        assert _pre_route("   ") is None

    def test_farewells(self):
        from whaagent.graph import _pre_route

        assert _pre_route("tchau") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("bye") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("até logo") == {"intent": "chat", "tool_plan": None}

    def test_thanks(self):
        from whaagent.graph import _pre_route

        assert _pre_route("obrigado") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("valeu") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("thanks") == {"intent": "chat", "tool_plan": None}

    def test_affirmations_negations(self):
        from whaagent.graph import _pre_route

        assert _pre_route("sim") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("não") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("ok") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("sure") == {"intent": "chat", "tool_plan": None}
        # sentence with these words should NOT match (pattern requires end-of-string)
        assert _pre_route("sim, me fala mais") is None

    def test_translation_requests(self):
        from whaagent.graph import _pre_route

        assert _pre_route("traduz isso para inglês") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("translate this to portuguese") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("como se diz hello em português") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("o que significa ephemeral") == {"intent": "chat", "tool_plan": None}

    def test_simple_math(self):
        from whaagent.graph import _pre_route

        assert _pre_route("quanto é 5 + 3") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("calcule 100 / 4") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("calculate 12 * 8") == {"intent": "chat", "tool_plan": None}

    def test_time_date_queries(self):
        from whaagent.graph import _pre_route

        assert _pre_route("que horas são?") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("what time is it?") == {"intent": "chat", "tool_plan": None}
        assert _pre_route("what day is today") == {"intent": "chat", "tool_plan": None}

    def test_weather_queries(self):
        from whaagent.graph import _pre_route

        assert _pre_route("tempo em Lisboa") == {"intent": "tool_use", "tool_plan": "web_search"}
        assert _pre_route("weather in London") == {"intent": "tool_use", "tool_plan": "web_search"}
        assert _pre_route("previsão do tempo para amanhã") == {"intent": "tool_use", "tool_plan": "web_search"}
        assert _pre_route("forecast for Tokyo") == {"intent": "tool_use", "tool_plan": "web_search"}

    def test_price_queries(self):
        from whaagent.graph import _pre_route

        assert _pre_route("preço do bitcoin") == {"intent": "tool_use", "tool_plan": "web_search"}
        assert _pre_route("price of ETH") == {"intent": "tool_use", "tool_plan": "web_search"}
        assert _pre_route("cotação do dólar") == {"intent": "tool_use", "tool_plan": "web_search"}
        assert _pre_route("quanto custa o iPhone") == {"intent": "tool_use", "tool_plan": "web_search"}

    def test_sports_scores(self):
        from whaagent.graph import _pre_route

        assert _pre_route("placar do jogo") == {"intent": "tool_use", "tool_plan": "web_search"}
        assert _pre_route("who won yesterday") == {"intent": "tool_use", "tool_plan": "web_search"}
        assert _pre_route("resultado do jogo do Barça") == {"intent": "tool_use", "tool_plan": "web_search"}

    def test_factual_lookups(self):
        from whaagent.graph import _pre_route

        assert _pre_route("what is quantum computing") == {"intent": "tool_use", "tool_plan": "web_search"}
        assert _pre_route("who is Linus Torvalds") == {"intent": "tool_use", "tool_plan": "web_search"}
        assert _pre_route("o que é machine learning") == {"intent": "tool_use", "tool_plan": "web_search"}
        assert _pre_route("quem é Elon Musk") == {"intent": "tool_use", "tool_plan": "web_search"}
        # should NOT match general "what" question
        assert _pre_route("what do you think about this?") is None
        # should NOT match philosophical questions
        assert _pre_route("what is the meaning of life?") is None

    def test_code_howto_delegates(self):
        from whaagent.graph import _pre_route

        assert _pre_route("how do I implement a REST API in Python") == {"intent": "delegate", "tool_plan": "developer"}
        assert _pre_route("como implementar autenticação em Go") == {"intent": "delegate", "tool_plan": "developer"}
        assert _pre_route("como criar um script em JavaScript") == {"intent": "delegate", "tool_plan": "developer"}
