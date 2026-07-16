# src/whaagent/tools/agent_invocation.py
"""Agent Invocation Tool for delegating tasks to other agents."""

import asyncio
import json
import logging
import os
from typing import Any

from whaagent.interfaces.base import Tool
from whaagent.registry import AgentRegistry

logger = logging.getLogger(__name__)


def _clear_langchain_httpx_cache() -> None:
    """Clear langchain_openai's LRU-cached httpx clients.

    ``langchain_openai.chat_models._client_utils`` caches async (and sync)
    ``httpx`` clients with ``@lru_cache`` so that every ``ChatOpenAI``
    instance reuses the same underlying ``httpx.AsyncClient``.  That
    client's ``asyncio.locks.Event`` objects are bound to the event loop
    that was active when the client was first *used*.  When a delegated
    agent runs inside a brand-new event loop (created in
    ``run_in_new_loop``), those bound locks cause::

        RuntimeError: <asyncio.locks.Event> is bound to a different event loop

    Calling this function before creating the delegated agent ensures a
    fresh ``httpx.AsyncClient`` is created in the new loop.
    """
    try:
        from langchain_openai.chat_models._client_utils import (
            _cached_async_httpx_client,
            _cached_sync_httpx_client,
        )

        _cached_async_httpx_client.cache_clear()
        _cached_sync_httpx_client.cache_clear()
    except ImportError:
        # langchain_openai not installed — nothing to clear.
        pass


# Agents that can be delegated to (excludes assistant and ollama to prevent recursion)
DELEGATABLE_AGENTS = [
    "developer",
    "learning",
    "news",
    "youtube",
    "committer",
    "github-pr-reviewer",
    "paywall-remover",
]

# Default timeout for agent invocations (seconds).
# Override with AGENT_INVOCATION_TIMEOUT env var.
_DEFAULT_AGENT_TIMEOUT = int(os.environ.get("AGENT_INVOCATION_TIMEOUT", "240"))


class AgentInvocationTool(Tool):
    """Tool to invoke other registered agents.

    This tool allows an orchestrator agent to delegate tasks to specialized
    agents. Each invocation creates a fresh agent instance with no prior
    conversation context.

    Input format (JSON string):
        {
            "agent_name": "developer",
            "prompt": "Analyze the auth module...",
            "timeout": 120  // optional, defaults to 120 (override with AGENT_INVOCATION_TIMEOUT env var)
        }

    Returns:
        The delegated agent's response as a string, or an error message.
    """

    @property
    def name(self) -> str:
        return "invoke_agent"

    @property
    def description(self) -> str:
        return """Invoke a specialized agent to handle a task.

The delegated agent starts with no conversation context - include all necessary
context in your prompt.

Available agents:
- developer: Code exploration, file operations, technical analysis
- learning: Educational tutorials, step-by-step guides, explanations
- news: Current news, events, breaking stories
- youtube: Video transcript extraction and analysis
- committer: Git commit message generation from code changes
- github-pr-reviewer: GitHub PR review with inline comments
- paywall-remover: Extract content from paywalled/blocked sites

Input (JSON):
{
    "agent_name": "developer",
    "prompt": "Your task with full context...",
    "timeout": 120
}

Returns the agent's response or an error message."""

    def invoke(self, input_str: str) -> str:
        """Execute agent invocation.

        Args:
            input_str: JSON string with agent_name, prompt, and optional timeout.

        Returns:
            Agent response or error message (never raises exceptions).
        """
        # Parse input
        try:
            data = json.loads(input_str)
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON input. Expected format: {{'agent_name': '...', 'prompt': '...'}}. Details: {e}"

        # Validate required fields
        if "agent_name" not in data:
            return "Error: Missing required field 'agent_name'. Available agents: " + ", ".join(DELEGATABLE_AGENTS)
        if "prompt" not in data:
            return "Error: Missing required field 'prompt'."

        agent_name = data["agent_name"]
        prompt = data["prompt"]
        timeout = data.get("timeout", _DEFAULT_AGENT_TIMEOUT)

        # Block self-delegation
        if agent_name == "ollama":
            available = ", ".join(DELEGATABLE_AGENTS)
            return f"Error: Ollama agent cannot delegate to itself. Choose a different agent: {available}"

        # Validate agent exists
        agent_cls = AgentRegistry.get(agent_name)
        if agent_cls is None:
            registered_agents = AgentRegistry.list_agents()
            delegatable = [a for a in registered_agents if a in DELEGATABLE_AGENTS]
            return f"Error: Agent '{agent_name}' not found. Available agents: {', '.join(delegatable)}"

        # Check agent is delegatable
        if agent_name not in DELEGATABLE_AGENTS:
            return f"Error: Agent '{agent_name}' cannot be delegated to. Available: {', '.join(DELEGATABLE_AGENTS)}"

        # Invoke agent in async context
        try:
            # Check if we're already in an async context (e.g., FastAPI/uvicorn)
            try:
                asyncio.get_running_loop()
                # We're in an async context, run in a thread to avoid blocking
                import threading

                result: list[str | None] = [None]
                exception: list[Exception | None] = [None]

                def run_in_new_loop() -> None:
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            _clear_langchain_httpx_cache()
                            result[0] = new_loop.run_until_complete(
                                self._invoke_agent_async(agent_cls, agent_name, prompt, timeout)
                            )
                        finally:
                            new_loop.close()
                    except Exception as e:
                        exception[0] = e

                thread = threading.Thread(target=run_in_new_loop)
                thread.start()
                thread.join(timeout=timeout + 5)  # Add buffer to the timeout

                if exception[0]:
                    raise exception[0]
                if result[0] is None:
                    return (
                        f"Error: Agent '{agent_name}' timed out after"
                        f" {timeout} seconds. DO NOT retry — the timeout is final."
                    )

                return result[0]
            except RuntimeError:
                # No running loop, use asyncio.run()
                _clear_langchain_httpx_cache()
                return asyncio.run(self._invoke_agent_async(agent_cls, agent_name, prompt, timeout))
        except Exception as e:
            logger.error(f"Agent invocation failed: {e}")
            return f"Error: Agent '{agent_name}' encountered an error: {e}"

    async def _invoke_agent_async(
        self,
        agent_cls: Any,
        agent_name: str,
        prompt: str,
        timeout: float,
    ) -> str:
        """Invoke agent asynchronously with timeout.

        Args:
            agent_cls: The agent class to instantiate.
            agent_name: Name of the agent (for tool categories lookup).
            prompt: The prompt to send to the agent.
            timeout: Timeout in seconds.

        Returns:
            Agent response or error message.
        """
        try:
            tool_categories = AgentRegistry.get_tool_categories(agent_name)
            agent = agent_cls(_agent_name=agent_name, tool_categories=tool_categories)
            result = await asyncio.wait_for(
                agent.run(prompt),
                timeout=timeout,
            )
            return str(result)
        except asyncio.TimeoutError:
            return (
                f"Error: Agent timed out after {timeout} seconds."
                " Try simplifying your request. DO NOT retry — the timeout is final."
            )
        except Exception as e:
            logger.error(f"Async agent invocation failed: {e}")
            raise
