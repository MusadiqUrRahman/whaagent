"""Base agent class for whaagent.

This module provides AgentBase, the main class for creating agents
with MCP tool integration and LLM provider abstraction.
"""

import asyncio
import logging
import time
from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Sequence, Union

from langchain.agents import create_agent
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from whaagent.config import get_config
from whaagent.interfaces.base import Agent
from whaagent.llm import _create_model, get_default_model
from whaagent.mcp import MCPProvider
from whaagent.prompts.generator import generate_system_prompt
from whaagent.tools.manifest import ToolManifest, ToolManifestClient

logger = logging.getLogger(__name__)


class AgentBase(Agent):
    """Reusable base class for LangGraph agents with optional MCP tools.

    This class provides the foundation for creating agents in whaagent. It
    handles LLM model creation, MCP tool integration, and graph initialization.

    Attributes:
        model: The LLM model instance.
        _mcp_provider: Optional MCP provider for external tool access.
        _initial_mcp_tools: Optional pre-loaded MCP tools.
        _thread_id: Thread ID for conversation memory.
        _tools: List of available tools (local + MCP).
        _graph: The agent graph, initialized lazily.

    Example:
        ```python
        from whaagent import AgentBase, AgentRegistry

        @AgentRegistry.register("my-agent")
        class MyAgent(AgentBase):
            @property
            def system_prompt(self) -> str:
                return "You are a helpful assistant."

            def local_tools(self) -> Sequence[Any]:
                return []  # Add local tools here
        ```
    """

    def __init__(
        self,
        model_name: str | None = None,
        temperature: float | None = None,
        mcp_provider: MCPProvider | None = None,
        initial_mcp_tools: List[Any] | None = None,
        thread_id: str = "1",
        checkpointer: Any | None = None,
        tool_categories: List[str] | None = None,
        toolbox_url: str | None = None,
        _agent_name: str | None = None,
        progress_callback: Any | None = None,
        mcp_server_names: list[str] | None = None,
        **kwargs: Any,
    ):
        """Initialize the agent.

        Args:
            model_name: Optional model name. If not provided, uses default from config.
            temperature: Optional temperature setting. If not provided, uses default from config.
            mcp_provider: Optional MCP provider for external tool access.
            initial_mcp_tools: Optional pre-loaded MCP tools.
            thread_id: Thread ID for conversation memory.
            checkpointer: Optional checkpointer for persistent memory.
            tool_categories: Optional list of tool categories to document in prompt (e.g., ["web", "git"]).
            toolbox_url: URL of the toolbox server for tool manifest fetching. If not provided,
                        uses TOOLBOX_URL env var or defaults to http://localhost:8080/sse.
            _agent_name: Internal agent name (set by registry when creating agents).
            progress_callback: Optional callback for progress updates.
            mcp_server_names: Optional list of MCP server names for persistent connections.
            **kwargs: Additional arguments (for future compatibility).
        """
        config = get_config()

        # Resolve agent name early (needed for model lookup)
        self._agent_name = _agent_name or config.agents.default_agent_name

        # Resolve model: agent config > global config > provider default
        if model_name is None:
            model_name = config.agent_models.get_model_for(self._agent_name) or config.llm.model or get_default_model()

        if temperature is None:
            temperature = config.llm.temperature

        self.model = _create_model(model_name, temperature)
        self._mcp_provider = mcp_provider
        self._initial_mcp_tools = initial_mcp_tools
        self._thread_id = thread_id
        self._checkpointer = checkpointer
        # Keep the checkpointer context manager alive so GC doesn't close
        # the underlying SQLite connection while the agent is pooled.
        self._checkpointer_ctx = kwargs.pop("_checkpointer_ctx", None)
        self._tools: List[Any] = list(self.local_tools())
        self._graph: Any | None = None
        self._init_lock = asyncio.Lock()
        self._tool_categories = tool_categories
        # Get toolbox_url from: parameter > config > default
        if toolbox_url is None:
            toolbox_url = config.mcp.toolbox_url or "http://localhost:8080"
        self._toolbox_url = toolbox_url
        self._tool_manifest: ToolManifest | None = None
        self._progress_callback = progress_callback
        self._mcp_server_names = mcp_server_names

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Prompt that defines agent behavior.

        Returns:
            The system prompt string.
        """

    def _get_system_prompt(self) -> str:
        """Get system prompt with complete tool documentation.

        Combines the agent's base system_prompt with tool documentation
        fetched from the toolbox server (if tool_categories are specified).

        Supports customization via config file (.whaagent.yaml):
        - agents.system_prompt_template: Direct template string
        - agents.system_prompt_file: Path to file containing template

        Returns:
            The complete system prompt string.
        """
        base_prompt = self.system_prompt

        # Check for custom system prompt template from config or file
        config = get_config()
        custom_prompt = None

        # Priority: config template > config file > agent's prompt
        if config.agents.system_prompt_template:
            custom_prompt = config.agents.system_prompt_template
            logger.debug("Using system prompt from config (agents.system_prompt_template)")
        elif hasattr(config.agents, "system_prompt_file") and config.agents.system_prompt_file:
            prompt_path = Path(config.agents.system_prompt_file)
            if prompt_path.exists():
                try:
                    custom_prompt = prompt_path.read_text(encoding="utf-8")
                    logger.debug(f"Using system prompt from config file: {prompt_path}")
                except Exception as e:
                    logger.warning(f"Failed to read system prompt file {prompt_path}: {e}")

        # If we have a manifest and tool categories, append tools section
        if self._tool_manifest is not None and self._tool_categories:
            try:
                effective_prompt = custom_prompt if custom_prompt is not None else base_prompt
                full_prompt = generate_system_prompt(
                    manifest=self._tool_manifest,
                    categories=self._tool_categories,
                    base_prompt=effective_prompt,
                )
                return full_prompt
            except Exception as e:
                logger.warning(f"Failed to generate system prompt with tools: {e}")

        # Use custom prompt if available, otherwise use agent's base prompt
        return custom_prompt if custom_prompt is not None else base_prompt

    def _get_node_models(self) -> dict[str, Any]:
        """Resolve per-node model instances for graph nodes.

        Returns:
            Dict mapping node names ("router", "agent") to model instances.
            Only includes nodes that have explicit overrides configured.
        """
        config = get_config()
        node_map = config.agent_models.node_overrides.get(self._agent_name, {})
        overrides: dict[str, Any] = {}
        for node in ("router", "agent"):
            node_model_name = node_map.get(node)
            if node_model_name:
                overrides[node] = _create_model(node_model_name, config.llm.temperature)
        return overrides

    def local_tools(self) -> Sequence[Any]:
        """Built-in tools available even without MCP.

        Returns:
            A sequence of local tool instances.
        """
        return []

    @classmethod
    def with_persistent_memory(
        cls,
        db_path: str | Path,
        **kwargs: Any,
    ) -> "AgentBase":
        """Create an agent with persistent SQLite-backed memory.

        This factory method creates an agent with a sync SqliteSaver checkpointer
        for persistent conversation history across restarts.

        WARNING: This uses the SYNC SqliteSaver, which is only works with
        synchronous LangGraph agents. For async agents (the default),
        use ``with_async_persistent_memory`` instead, which supports
        async methods like ``aget_tuple`` and ``ainvoke``.

        Args:
            db_path: Path to SQLite database for checkpoint storage.
            **kwargs: Additional arguments passed to the agent's __init__.

        Returns:
            An agent instance with SqliteSaver checkpointer.

        Example:
            ```python
            from whaagent import AgentBase

            # Sync usage only (e.g., CLI)
            agent = MyAgent.with_persistent_memory(
                db_path="~/conversations.db",
                model_name="gpt-4",
            )
            ```
        """
        from whaagent.storage.database import Database

        db = Database(Path(db_path))
        kwargs["checkpointer"] = db.get_checkpointer()
        return cls(**kwargs)

    @classmethod
    async def with_async_persistent_memory(
        cls,
        db_path: str | Path,
        **kwargs: Any,
    ) -> "AgentBase":
        """Create an agent with async persistent SQLite-backed memory.

        Use this for async agents that need checkpoint support
        (like the WhatsApp webhook handlers). Uses AsyncSqliteSaver
        which supports async methods.

        Args:
            db_path: Path to SQLite database for checkpoint storage.
            **kwargs: Additional arguments passed to the agent's __init__.

        Returns:
            An agent instance with AsyncSqliteSaver checkpointer.

        Example:
            ```python
            agent = await MyAgent.with_async_persistent_memory(
                db_path="~/conversations.db",
            )
            ```
        """
        from whaagent.storage.database import Database

        db = Database(Path(db_path))
        async with await db.get_async_checkpointer() as checkpointer:
            kwargs["checkpointer"] = checkpointer
            return cls(**kwargs)

    async def _load_mcp_tools(self) -> List[Any]:
        """Load MCP tools from the provider.

        Returns:
            A list of MCP tools, or empty list if no provider.
        """
        if self._initial_mcp_tools is not None:
            return list(self._initial_mcp_tools)
        if self._mcp_provider is None:
            return []
        return await self._mcp_provider.get_tools()

    async def _fetch_tool_manifest(self) -> ToolManifest | None:
        """Fetch tool manifest from toolbox server with graceful degradation.

        Returns:
            ToolManifest if successful, None if toolbox unavailable.

        Note:
            This method implements graceful degradation - if the toolbox server
            is unavailable, the agent will continue to function with local tools only.
            Failures are logged but do not prevent agent initialization.
        """
        if not self._tool_categories:
            return None

        try:
            client = ToolManifestClient(self._toolbox_url)
            manifest = await client.get_manifest()
            logger.debug(f"Fetched manifest with {len(manifest.tools)} tools from toolbox")
            return manifest
        except ConnectionError as e:
            logger.warning(
                f"Toolbox server at {self._toolbox_url} unavailable: {e}. Agent will run with local tools only."
            )
            return None
        except Exception as e:
            logger.warning(
                f"Failed to fetch tool manifest from {self._toolbox_url}: {e}. Agent will run with local tools only."
            )
            return None

    async def _ensure_initialized(self) -> None:
        """Ensure the agent graph is initialized.

        Lazily initializes the graph, loads MCP tools, and fetches tool manifest.
        """
        if self._graph is not None:
            return

        async with self._init_lock:
            # Double-checked locking
            if self._graph is not None:
                return

            start = time.monotonic()

            # Fetch tool manifest if categories specified
            if self._tool_manifest is None and self._tool_categories:
                self._tool_manifest = await self._fetch_tool_manifest()

            # Get system prompt (potentially with tools)
            system_prompt = self._get_system_prompt()

            # Load MCP tools — use persistent provider if mcp_server_names given
            if self._mcp_server_names and self._mcp_provider is None:
                self._mcp_provider = MCPProvider(server_names=self._mcp_server_names)
                mcp_tools = await self._mcp_provider.get_tools()
                self._tools.extend(mcp_tools)
            else:
                self._tools.extend(await self._load_mcp_tools())

            self._graph = self._create_graph(
                model=self.model,
                tools=self._tools,
                system_prompt=system_prompt,
                checkpointer=self._checkpointer or InMemorySaver(),
            )

            elapsed = time.monotonic() - start
            logger.info("[timing] agent_init=%.1fs agent=%s", elapsed, self._agent_name)

    def _create_graph(
        self,
        model: Any,
        tools: list[Any],
        system_prompt: str,
        checkpointer: Any,
    ) -> Any:
        """Create the agent graph. Override in subclasses for custom graphs.

        Args:
            model: LLM model instance.
            tools: List of available tools.
            system_prompt: System prompt string.
            checkpointer: Checkpointer for persistent memory.

        Returns:
            A compiled graph with ainvoke().
        """
        return create_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            checkpointer=checkpointer,
        )

    def _normalize_messages(self, input_data: Union[str, List[BaseMessage]]) -> List[BaseMessage]:
        """Normalize input data to a list of BaseMessage.

        Args:
            input_data: Either a string or a list of BaseMessage.

        Returns:
            A list of BaseMessage objects.
        """
        if isinstance(input_data, str):
            return [HumanMessage(content=input_data)]
        return input_data

    def _default_config(self) -> Dict[str, Any]:
        """Get the default configuration for the agent graph.

        Returns:
            A dictionary with the thread_id configuration.
        """
        return {"configurable": {"thread_id": self._thread_id}}

    async def run(
        self,
        input_data: Union[str, List[BaseMessage]],
        config: Dict[str, Any] | None = None,
    ) -> Union[str, BaseMessage]:
        """Run the agent with the given input.

        Args:
            input_data: The input for the agent, either a string or a list of messages.
            config: Optional configuration for the agent run.

        Returns:
            The agent's response as a string or BaseMessage.

        Raises:
            RuntimeError: If the agent graph fails to initialize.
        """
        await self._ensure_initialized()

        if self._graph is None:
            raise RuntimeError("Agent graph failed to initialize.")

        try:
            effective_thread = (
                (config or {}).get("configurable", {}).get("thread_id", self._thread_id)
                if isinstance(config, dict)
                else self._thread_id
            )
            logger.info("[context] agent.run: agent=%s thread_id=%s", self._agent_name, effective_thread)
            result = await self._graph.ainvoke(
                {"messages": self._normalize_messages(input_data)},
                config=config or self._default_config(),
            )
            # Prefer final_response from custom graphs (e.g. Responder node)
            if result.get("final_response"):
                return str(result["final_response"])
            return str(result["messages"][-1].content)
        except BaseException as e:
            # Check if this is purely a tool execution error wrapped in ExceptionGroups.
            # Tool errors should be non-fatal — return the error so the caller can retry.
            tool_errors = self._extract_tool_errors(e)
            if tool_errors:
                error_summary = "; ".join(tool_errors)
                logger.warning(
                    "Tool execution failed for agent '%s': %s",
                    self._agent_name,
                    error_summary,
                )
                return f"Tool error: {error_summary}"

            # Non-tool errors — log full trace and re-raise
            def _unwrap(exc: BaseException, depth: int = 0) -> str:
                if hasattr(exc, "exceptions") and exc.exceptions:
                    inner = [_unwrap(sub, depth + 1) for sub in exc.exceptions]
                    prefix = "  " * depth
                    return f"{prefix}{type(exc).__name__}:\n" + "\n".join(inner)
                return f"{'  ' * depth}{type(exc).__name__}: {exc}"

            logger.error(
                "Agent run failed for agent '%s':\n%s",
                self._agent_name,
                _unwrap(e),
            )
            raise

    @staticmethod
    def _extract_tool_errors(exc: BaseException) -> list[str]:
        """Recursively extract ToolException messages from nested ExceptionGroups.

        Returns an empty list if any non-tool exception is found (meaning the
        error is not purely a tool failure).
        """
        from langchain_core.exceptions import OutputParserException

        tool_errors: list[str] = []
        queue: list[BaseException] = [exc]

        while queue:
            current = queue.pop(0)
            # ExceptionGroup / BaseExceptionGroup — recurse into sub-exceptions
            if hasattr(current, "exceptions") and current.exceptions:
                queue.extend(current.exceptions)
            # Tool execution error — collect it
            elif "ToolException" in type(current).__name__ or "tool" in type(current).__name__.lower():
                tool_errors.append(str(current))
            # OutputParser errors are also recoverable (model produced bad format)
            elif isinstance(current, OutputParserException):
                tool_errors.append(str(current))
            # Anything else means this isn't a pure tool failure
            else:
                return []

        return tool_errors

    async def run_with_memory(
        self,
        input_data: Union[str, List[BaseMessage]],
        *,
        thread_id: str | None = None,
        max_tokens: int | None = None,
    ) -> Union[str, BaseMessage]:
        """Run agent with conversation memory support.

        This is a convenience method that runs the agent with an explicit
        thread ID for persistent conversation history. The agent must be
        initialized with a persistent checkpointer (e.g., SqliteSaver)
        for history to persist across runs.

        Args:
            input_data: The input for the agent.
            thread_id: Optional thread ID override for conversation scoping.
                If not provided, uses the agent's default thread_id.
            max_tokens: Optional max tokens for context window.
                NOTE: Not yet implemented - reserved for future token truncation.

        Returns:
            The agent's response as a string or BaseMessage.
        """
        config = self._default_config()

        if thread_id is not None:
            config["configurable"]["thread_id"] = thread_id

        # TODO: Implement token truncation if max_tokens is provided
        # This would require fetching checkpoint history and trimming
        # to stay within the token limit.

        return await self.run(input_data, config=config)

    def get_tools(self) -> List[Any]:
        """Get the list of available tools.

        Returns:
            A copy of the tools list to prevent external modification.
        """
        return list(self._tools)
