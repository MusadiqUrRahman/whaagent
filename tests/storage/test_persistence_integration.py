from typing import Any
from unittest.mock import patch

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from whaagent.agent import AgentBase
from whaagent.storage.database import Database


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_persistence.db"


@pytest.fixture
def db(db_path):
    return Database(db_path)


class SimpleAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        return "You are a helpful assistant. Keep your answers very short."


class _ContextAwareFakeLLM(BaseChatModel):
    """Provider-agnostic fake LLM that returns deterministic responses based on message content.

    Subclassing BaseChatModel ensures full compatibility with LangChain's
    create_agent() and bind_tools() internals without hitting any real API.
    """

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        content = messages[-1].content if messages else ""
        if "name is" in content:
            name = content.split("name is")[-1].strip(".")
            reply = f"Hello {name}!"
        elif "What is my name" in content:
            names = [m.content.split("name is")[-1].strip(".") for m in messages if "name is" in m.content]
            reply = f"Your name is {names[0]}." if names else "I don't know your name."
        elif "favorite color is" in content:
            color = content.split("favorite color is")[-1].strip(".")
            reply = f"I remembered your favorite color is {color}."
        elif "What is my favorite color" in content:
            colors = [
                m.content.split("favorite color is")[-1].strip(".")
                for m in messages
                if "favorite color is" in m.content
            ]
            reply = f"Your favorite color is {colors[0]}." if colors else "I don't know."
        else:
            reply = "I am a mock response."
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=reply))])


@pytest.mark.asyncio
async def test_agent_persistence(db, db_path):
    """Test that an agent can remember context across different instances using the same DB."""
    thread_id = "test-session-123"
    fake_llm = _ContextAwareFakeLLM()

    with patch("whaagent.agent._create_model", return_value=fake_llm):
        async with await db.get_async_checkpointer() as checkpointer1:
            agent1 = SimpleAgent(thread_id=thread_id, checkpointer=checkpointer1)
            response1 = await agent1.run("My name is whaagent Test.")
            assert "whaagent Test" in str(response1)

        # Simulate "process restart" with a fresh DB instance on the same file
        db2 = Database(db_path)
        async with await db2.get_async_checkpointer() as checkpointer2:
            agent2 = SimpleAgent(thread_id=thread_id, checkpointer=checkpointer2)
            response2 = await agent2.run("What is my name?")
            assert "whaagent Test" in str(response2)


@pytest.mark.asyncio
async def test_different_threads_isolation(db):
    """Test that different thread IDs have isolated memories."""
    fake_llm = _ContextAwareFakeLLM()

    with patch("whaagent.agent._create_model", return_value=fake_llm):
        async with await db.get_async_checkpointer() as checkpointer:
            agent_a = SimpleAgent(thread_id="thread-a", checkpointer=checkpointer)
            await agent_a.run("My favorite color is Blue.")

            agent_b = SimpleAgent(thread_id="thread-b", checkpointer=checkpointer)
            await agent_b.run("My favorite color is Red.")

            resp_a = await agent_a.run("What is my favorite color?")
            resp_b = await agent_b.run("What is my favorite color?")

            assert "blue" in str(resp_a).lower()
            assert "red" in str(resp_b).lower()
            assert "red" not in str(resp_a).lower()
            assert "blue" not in str(resp_b).lower()
