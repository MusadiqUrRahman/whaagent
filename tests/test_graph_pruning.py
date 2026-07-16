"""Tests for message pruning helpers: _budget_window_messages, _build_prune_removes,
and the summarize_node."""

import time
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage

from whaagent.graph import (
    AgentState,
    summarize_node,
)


class TestBudgetWindowMessages:
    """Tests for _budget_window_messages — character-budget-based windowing."""

    def test_empty_returns_empty(self) -> None:
        """Empty message list should return empty list."""
        from whaagent.graph import _budget_window_messages

        assert _budget_window_messages([], 1000) == []

    def test_single_msg_within_budget(self) -> None:
        """Single message within budget should return that message."""
        from whaagent.graph import _budget_window_messages

        msgs = [HumanMessage(content="Hello")]
        result = _budget_window_messages(msgs, 1000)
        assert len(result) == 1
        assert result[0].content == "Hello"

    def test_single_msg_exceeds_budget_still_returned(self) -> None:
        """Single message exceeding budget should still be returned (guarantee)."""
        from whaagent.graph import _budget_window_messages

        msgs = [HumanMessage(content="x" * 5000)]
        result = _budget_window_messages(msgs, 1000)
        assert len(result) == 1
        assert result[0].content == "x" * 5000

    def test_truncates_when_budget_exceeded(self) -> None:
        """Should truncate when cumulative budget is exceeded."""
        from whaagent.graph import _budget_window_messages

        msgs = [
            HumanMessage(content="a" * 1000),
            AIMessage(content="b" * 500),
            HumanMessage(content="c" * 600),
        ]
        result = _budget_window_messages(msgs, 1500)
        # Should include last message (600) + second-to-last (500) = 1100 budget
        # First message (1000) would exceed budget: 1100 + 1000 = 2100 > 1500
        assert len(result) == 2
        assert result[0].content == "b" * 500
        assert result[1].content == "c" * 600

    def test_preserves_order(self) -> None:
        """Should preserve original message order (most recent last)."""
        from whaagent.graph import _budget_window_messages

        msgs = [
            HumanMessage(content="first"),
            AIMessage(content="second"),
            HumanMessage(content="third"),
        ]
        result = _budget_window_messages(msgs, 10000)
        assert len(result) == 3
        assert result[0].content == "first"
        assert result[1].content == "second"
        assert result[2].content == "third"

    def test_hard_ceiling_on_count(self) -> None:
        """Should enforce max_messages ceiling even if budget allows more."""
        from whaagent.graph import _budget_window_messages

        # 30 tiny messages, each 10 chars = 300 total (well under 10K budget)
        # But max_messages=20 should cap at 20
        msgs = [HumanMessage(content=f"msg{i}") for i in range(30)]
        result = _budget_window_messages(msgs, 10000, max_messages=20)
        assert len(result) == 20
        # Should be the 20 most recent
        assert result[0].content == "msg10"
        assert result[-1].content == "msg29"

    def test_mixed_human_ai_messages(self) -> None:
        """Should handle mixed HumanMessage and AIMessage correctly."""
        from whaagent.graph import _budget_window_messages

        msgs = [
            HumanMessage(content="Q1"),
            AIMessage(content="A1"),
            HumanMessage(content="Q2"),
            AIMessage(content="A2"),
        ]
        result = _budget_window_messages(msgs, 100)
        assert len(result) == 4
        assert isinstance(result[0], HumanMessage)
        assert isinstance(result[1], AIMessage)
        assert isinstance(result[2], HumanMessage)
        assert isinstance(result[3], AIMessage)


class TestBuildPruneRemoves:
    """Tests for _build_prune_removes helper — returns RemoveMessage list for old messages."""

    def test_returns_empty_when_within_cap(self) -> None:
        """5 messages with cap 20 → no pruning needed."""
        from whaagent.graph import _build_prune_removes

        msgs = [HumanMessage(content=f"msg {i}", id=f"msg-{i}") for i in range(5)]
        assert _build_prune_removes(msgs, max_messages=20) == []

    def test_returns_removes_for_excess_messages(self) -> None:
        """25 messages with cap 20 → 5 RemoveMessage objects."""
        from whaagent.graph import _build_prune_removes

        msgs = [HumanMessage(content=f"msg {i}", id=f"msg-{i}") for i in range(25)]
        removes = _build_prune_removes(msgs, max_messages=20)
        assert len(removes) == 5
        assert all(isinstance(r, RemoveMessage) for r in removes)

    def test_preserves_most_recent_messages(self) -> None:
        """Oldest messages are removed, newest kept."""
        from whaagent.graph import _build_prune_removes

        msgs = [HumanMessage(content=f"msg {i}", id=f"msg-{i}") for i in range(25)]
        removes = _build_prune_removes(msgs, max_messages=20)
        removed_ids = {r.id for r in removes}
        # Should remove msg-0 through msg-4 (oldest 5)
        assert removed_ids == {f"msg-{i}" for i in range(5)}
        # Should NOT remove msg-5 through msg-24 (newest 20)
        kept_ids = {f"msg-{i}" for i in range(5, 25)}
        assert removed_ids.isdisjoint(kept_ids)

    def test_skips_messages_without_ids(self) -> None:
        """Messages with id=None should be skipped safely."""
        from whaagent.graph import _build_prune_removes

        msgs = [HumanMessage(content=f"msg {i}") for i in range(25)]  # No explicit IDs
        removes = _build_prune_removes(msgs, max_messages=20)
        assert removes == []

    def test_empty_state_returns_empty(self) -> None:
        """0 messages → no pruning."""
        from whaagent.graph import _build_prune_removes

        assert _build_prune_removes([], max_messages=20) == []

    def test_exact_cap_returns_empty(self) -> None:
        """Exactly 20 messages → no pruning."""
        from whaagent.graph import _build_prune_removes

        msgs = [HumanMessage(content=f"msg {i}", id=f"msg-{i}") for i in range(20)]
        assert _build_prune_removes(msgs, max_messages=20) == []


class TestSummarizeNode:
    """Tests for summarize_node — conversation history compression."""

    @pytest.mark.asyncio
    async def test_noop_below_threshold(self) -> None:
        """Messages under token threshold should return empty dict (no-op)."""
        mock_model = AsyncMock()
        state: AgentState = {
            "messages": [HumanMessage(content="hello")],
            "intent": "",
            "tool_plan": None,
            "progress": [],
            "final_response": None,
        }

        result = await summarize_node(state, {}, model=mock_model)

        # No-op: model should NOT be called, empty dict returned
        mock_model.ainvoke.assert_not_called()
        assert result == {}

    @pytest.mark.asyncio
    async def test_noop_with_empty_messages(self) -> None:
        """Empty messages should return empty dict (no-op)."""
        mock_model = AsyncMock()
        state: AgentState = {
            "messages": [],
            "intent": "",
            "tool_plan": None,
            "progress": [],
            "final_response": None,
        }

        result = await summarize_node(state, {}, model=mock_model)
        mock_model.ainvoke.assert_not_called()
        assert result == {}

    @pytest.mark.asyncio
    async def test_summarizes_above_threshold(self) -> None:
        """Messages above threshold should be summarized and old ones removed."""
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="User asked about F1 news and weather in Tokyo."))

        # Build messages with IDs so RemoveMessage can target them
        msgs = [
            HumanMessage(content="What's the F1 news?" + " detail" * 200, id="msg-0"),
            AIMessage(content="Here are the F1 results..." + " detail" * 200, id="msg-1"),
            HumanMessage(content="And the weather in Tokyo?" + " detail" * 200, id="msg-2"),
            AIMessage(content="Tokyo is 22°C sunny." + " detail" * 200, id="msg-3"),
            HumanMessage(content="What about Paris?", id="msg-4"),
        ]

        state: AgentState = {
            "messages": msgs,
            "intent": "",
            "tool_plan": None,
            "progress": [],
            "final_response": None,
        }

        result = await summarize_node(state, {}, model=mock_model, max_tokens=10, keep_recent=2)

        # Model should have been called to summarize
        mock_model.ainvoke.assert_called_once()

        # Should return RemoveMessage for old messages (all except last 2)
        removes = [m for m in result.get("messages", []) if isinstance(m, RemoveMessage)]
        assert len(removes) == 3, f"Expected 3 RemoveMessage (msg-0,1,2), got {len(removes)}"
        removed_ids = {r.id for r in removes}
        assert "msg-0" in removed_ids
        assert "msg-1" in removed_ids
        assert "msg-2" in removed_ids

        # Context should have running_summary
        assert "context" in result
        assert "running_summary" in result["context"]
        assert "F1" in result["context"]["running_summary"]
        assert "summary_updated_at" in result["context"]

    @pytest.mark.asyncio
    async def test_extends_existing_summary(self) -> None:
        """Should extend an existing summary rather than recreate from scratch."""
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Extended: User also asked about chess."))

        msgs = [
            HumanMessage(content="Tell me about chess openings" + " detail" * 200, id="old-0"),
            AIMessage(content="Here are chess openings..." + " detail" * 200, id="old-1"),
            HumanMessage(content="New question"),
        ]

        state: AgentState = {
            "messages": msgs,
            "intent": "",
            "tool_plan": None,
            "progress": [],
            "final_response": None,
            "context": {
                "running_summary": "User asked about F1 news.",
                "summary_updated_at": time.time(),
            },
        }

        result = await summarize_node(state, {}, model=mock_model, max_tokens=10, keep_recent=1)

        # The prompt sent to LLM should mention the existing summary
        call_args = mock_model.ainvoke.call_args[0][0]
        prompt_text = str(call_args[0].content)
        assert "F1 news" in prompt_text, "Prompt should include existing summary"
        assert "updating" in prompt_text, "Prompt should ask to update existing summary"

        assert "chess" in result["context"]["running_summary"]

    @pytest.mark.asyncio
    async def test_ttl_expires_stale_summary(self) -> None:
        """Summary older than TTL should be cleared, summarization starts fresh."""
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Fresh summary about chess."))

        msgs = [
            HumanMessage(content="Chess question" + " detail" * 200, id="m-0"),
            AIMessage(content="Chess answer" + " detail" * 200, id="m-1"),
            HumanMessage(content="New question"),
        ]

        # Summary is 48 hours old (TTL default is 24h)
        stale_time = time.time() - (48 * 3600)

        state: AgentState = {
            "messages": msgs,
            "intent": "",
            "tool_plan": None,
            "progress": [],
            "final_response": None,
            "context": {
                "running_summary": "Stale summary about old topics.",
                "summary_updated_at": stale_time,
            },
        }

        await summarize_node(state, {}, model=mock_model, max_tokens=10, keep_recent=1)

        # The prompt should NOT mention the stale summary
        call_args = mock_model.ainvoke.call_args[0][0]
        prompt_text = str(call_args[0].content)
        assert "Stale summary" not in prompt_text, "Stale summary should not be used"
        assert "Summarize" in prompt_text, "Should start fresh with 'Summarize'"

    @pytest.mark.asyncio
    async def test_llm_failure_graceful_degradation(self) -> None:
        """When summarization LLM fails, should return empty dict (no crash)."""
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(side_effect=RuntimeError("API timeout"))

        msgs = [
            HumanMessage(content="Long message" + " detail" * 200, id="m-0"),
            AIMessage(content="Long response" + " detail" * 200, id="m-1"),
            HumanMessage(content="New question"),
        ]

        state: AgentState = {
            "messages": msgs,
            "intent": "",
            "tool_plan": None,
            "progress": [],
            "final_response": None,
        }

        # Should NOT raise — graceful degradation
        result = await summarize_node(state, {}, model=mock_model, max_tokens=10, keep_recent=1)
        assert result == {}, "Should return empty dict on LLM failure"

    @pytest.mark.asyncio
    async def test_context_missing_defaults_to_empty(self) -> None:
        """Missing context field should default to empty dict gracefully."""
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Summary of the conversation."))

        msgs = [
            HumanMessage(content="Big message" + " detail" * 200, id="m-0"),
            AIMessage(content="Big answer" + " detail" * 200, id="m-1"),
            HumanMessage(content="New question"),
        ]

        # No context field at all
        state: AgentState = {
            "messages": msgs,
            "intent": "",
            "tool_plan": None,
            "progress": [],
            "final_response": None,
        }

        result = await summarize_node(state, {}, model=mock_model, max_tokens=10, keep_recent=1)
        assert "context" in result
        assert "running_summary" in result["context"]

    @pytest.mark.asyncio
    async def test_filters_meta_responses(self) -> None:
        """AI meta-responses about capabilities should be excluded from summarization."""
        from whaagent.graph import summarize_node

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="- User asked about F1\n- Discussed weather"))

        msgs = [
            HumanMessage(content="Tell me about F1" + " detail" * 200, id="m-0"),
            AIMessage(
                content="I don't have access to previous messages, but I can see all 20 messages in this thread."
                + " detail" * 200,
                id="m-1",
            ),
            AIMessage(content="F1 results: Verstappen won" + " detail" * 200, id="m-2"),
            HumanMessage(content="New question"),
        ]

        state: AgentState = {
            "messages": msgs,
            "intent": "",
            "tool_plan": None,
            "progress": [],
            "final_response": None,
        }

        await summarize_node(state, {}, model=mock_model, max_tokens=10, keep_recent=1)

        # The prompt sent to LLM should NOT contain the meta-response
        call_args = mock_model.ainvoke.call_args[0][0]
        prompt_text = str(call_args[0].content)
        assert "I don't have access to previous" not in prompt_text
        assert "F1 results" in prompt_text

    @pytest.mark.asyncio
    async def test_all_meta_responses_skips_summarization(self) -> None:
        """If all old messages are meta-responses, skip summarization entirely."""
        from whaagent.graph import summarize_node

        mock_model = AsyncMock()
        msgs = [
            AIMessage(
                content="I don't have a specific number of messages. My context window is quite large."
                + " detail" * 200,
                id="m-0",
            ),
            AIMessage(
                content="I can 'remember' many turns. I don't have a permanent long-term memory." + " detail" * 200,
                id="m-1",
            ),
            HumanMessage(content="New question"),
        ]

        state: AgentState = {
            "messages": msgs,
            "intent": "",
            "tool_plan": None,
            "progress": [],
            "final_response": None,
        }

        result = await summarize_node(state, {}, model=mock_model, max_tokens=10, keep_recent=1)
        # Model should NOT be called — all old messages were filtered
        mock_model.ainvoke.assert_not_called()
        assert result == {}
