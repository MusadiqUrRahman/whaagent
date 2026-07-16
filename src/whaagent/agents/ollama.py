# src/whaagent/agents/ollama.py
"""Ollama Agent using local GLM-4.7-Flash model.

This agent uses LocalReasoningLLM to connect to a local Ollama server
running GLM-4.7-Flash with thinking tags automatically stripped from responses.
It serves as a versatile orchestrator capable of delegating to other agents.
"""

from typing import Any, Sequence

from whaagent.agent import AgentBase
from whaagent.llm.local_reasoning import get_local_developer_model
from whaagent.prompts import load_prompt
from whaagent.registry import AgentRegistry
from whaagent.tools import AgentInvocationTool


@AgentRegistry.register(
    "ollama",
    mcp_servers=["toolbox"],
    tool_categories=["web", "hackernews", "document", "git", "search", "media"],
)
class OllamaAgent(AgentBase):
    """Agent using local GLM-4.7-Flash model via Ollama.

    A versatile local AI orchestrator that can:
    - Search the web and fetch content via toolbox MCP tools
    - Delegate to specialized agents (developer, learning, news, youtube)
    - Handle research, writing, and analysis tasks directly

    MCP Servers:
        toolbox: Centralized tool server with web search, fetch, and more

    Server Configuration:
        Make sure toolbox is running:
        cd whaagent-toolkit && uv run toolbox-server

    Usage:
        whaagent ollama -i "Your question here"
    """

    def __init__(self) -> None:
        """Initialize OllamaAgent with local GLM-4.7-Flash model."""
        # Store custom model before calling parent init
        self._custom_model = get_local_developer_model()
        # Parent sets self.model, so we provide a property to return our custom one
        super().__init__()

    @property
    def system_prompt(self) -> str:
        """Return the orchestrator system prompt."""
        return load_prompt("ollama")

    @property
    def model(self) -> Any:
        """Return the custom LocalReasoningLLM model.

        Overrides parent's model to use LocalReasoningLLM that strips
        <reasoning>...</reasoning> tags from responses.
        """
        return self._custom_model

    @model.setter
    def model(self, value: Any) -> None:
        """No-op setter to allow parent's __init__ to set self.model."""
        pass

    def local_tools(self) -> Sequence[Any]:
        """Return local tools including agent invocation."""
        return [AgentInvocationTool().to_langchain_tool()]
