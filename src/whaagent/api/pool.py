"""Tenant-scoped agent pool for reusing agent instances across requests."""

import asyncio
import logging
from typing import Any

from whaagent.agent import AgentBase

logger = logging.getLogger(__name__)


class TenantAgentPool:
    """Pool of agent instances keyed by tenant_id:agent_name.

    Agents are created on first access and reused across requests.
    LRU eviction when pool exceeds max_size.
    """

    def __init__(self, max_size: int = 10) -> None:
        self._agents: dict[str, AgentBase] = {}
        self._access_order: list[str] = []
        self._lock = asyncio.Lock()
        self.max_size = max_size

    def __len__(self) -> int:
        return len(self._agents)

    async def get_or_create(
        self,
        tenant_id: str,
        agent_name: str,
        agent_cls: type,
        agent_kwargs: dict[str, Any],
    ) -> AgentBase:
        """Get a pooled agent or create one if not cached.

        Args:
            tenant_id: Tenant identifier.
            agent_name: Agent name (e.g., "assistant").
            agent_cls: Agent class to instantiate.
            agent_kwargs: Keyword arguments for agent constructor.

        Returns:
            Agent instance (pooled or freshly created).
        """
        key = f"{tenant_id}:{agent_name}"

        if key in self._agents:
            self._touch(key)
            logger.debug(f"[pool] reuse agent: {key}")
            return self._agents[key]

        async with self._lock:
            # Double-checked locking
            if key in self._agents:
                self._touch(key)
                return self._agents[key]

            await self._evict_if_needed()
            agent = await self._create(agent_cls, agent_kwargs)
            self._agents[key] = agent
            self._access_order.append(key)
            logger.info(f"[pool] created agent: {key} (pool_size={len(self._agents)})")
            return agent

    async def _create(
        self,
        agent_cls: type,
        agent_kwargs: dict[str, Any],
    ) -> AgentBase:
        """Create and initialize a new agent instance.

        Args:
            agent_cls: Agent class to instantiate.
            agent_kwargs: Constructor arguments.

        Returns:
            Initialized agent with MCP tools loaded.
        """
        # Extract db_path from agent_kwargs for checkpointer creation
        db_path = agent_kwargs.pop("db_path", None)

        if db_path:
            # Create persistent AsyncSqliteSaver for this agent instance
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

            # Create the saver context manager
            saver_ctx = AsyncSqliteSaver.from_conn_string(db_path)
            # Enter the context manager to initialize the connection
            checkpointer = await saver_ctx.__aenter__()
            # Store the context manager for cleanup when agent is evicted
            agent_kwargs["_checkpointer_ctx"] = saver_ctx
            agent_kwargs["checkpointer"] = checkpointer
        elif "checkpointer" not in agent_kwargs:
            # Create a default in-memory checkpointer if none provided
            from langgraph.checkpoint.memory import InMemorySaver

            agent_kwargs["checkpointer"] = InMemorySaver()

        agent: AgentBase = agent_cls(**agent_kwargs)
        # Trigger lazy initialization (MCP connection, graph compilation)
        await agent._ensure_initialized()
        return agent

    def _touch(self, key: str) -> None:
        """Move key to end of access order (most recently used)."""
        if key in self._access_order:
            self._access_order.remove(key)
            self._access_order.append(key)

    async def _evict_if_needed(self) -> None:
        """Evict oldest entry if pool is at capacity."""
        while len(self._agents) >= self.max_size and self._access_order:
            oldest_key = self._access_order.pop(0)
            agent = self._agents.pop(oldest_key, None)
            if agent:
                await self._safe_cleanup(agent, oldest_key)
            logger.info(f"[pool] evicted agent: {oldest_key}")

    @staticmethod
    async def _safe_cleanup(agent: AgentBase, key: str) -> None:
        """Safely clean up an evicted agent."""
        try:
            # Clean up checkpointer context manager if it exists
            if hasattr(agent, "_checkpointer_ctx"):
                try:
                    await agent._checkpointer_ctx.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"[pool] checkpointer cleanup failed for {key}: {e}")

            # Clean up agent if it has a cleanup method
            if hasattr(agent, "cleanup"):
                await agent.cleanup()  # type: ignore[attr-defined]
        except Exception as e:
            logger.warning(f"[pool] cleanup failed for {key}: {e}")

    async def evict(self, tenant_id: str, agent_name: str) -> None:
        """Manually evict an agent (e.g., after MCP connection failure).

        Args:
            tenant_id: Tenant identifier.
            agent_name: Agent name.
        """
        key = f"{tenant_id}:{agent_name}"
        agent = self._agents.pop(key, None)
        if key in self._access_order:
            self._access_order.remove(key)
        if agent:
            await self._safe_cleanup(agent, key)
        logger.info(f"[pool] manually evicted: {key}")

    async def validate_connections(self) -> list[str]:
        """Check MCP connections for all pooled agents.

        Returns list of keys for agents with stale connections.
        Does NOT evict — caller decides what to do.
        """
        stale: list[str] = []
        for key, agent in list(self._agents.items()):
            provider = getattr(agent, "_mcp_provider", None)
            if provider is None:
                continue
            try:
                tools = await provider.get_tools()
                if not tools:
                    logger.warning(f"[pool] {key}: MCP returned empty tool list")
            except Exception as e:
                logger.warning(f"[pool] {key}: stale MCP connection: {e}")
                stale.append(key)
        return stale

    async def warmup(
        self,
        configs: list[dict[str, Any]],
    ) -> None:
        """Pre-create agents for known tenants at startup.

        Creates agents eagerly so the first real request hits a warmed pool.
        Failures are logged per-agent but don't prevent others from warming up.

        Args:
            configs: List of dicts with keys: tenant_id, agent_name, agent_cls, agent_kwargs.
        """
        for cfg in configs:
            key = f"{cfg['tenant_id']}:{cfg['agent_name']}"
            if key in self._agents:
                logger.debug(f"[pool] warmup: skipping existing {key}")
                continue
            try:
                agent = await self._create(cfg["agent_cls"], dict(cfg["agent_kwargs"]))
                self._agents[key] = agent
                self._access_order.append(key)
                logger.info(f"[pool] warmed up: {key} (pool_size={len(self._agents)})")
            except Exception as e:
                logger.warning(f"[pool] warmup failed for {key}: {e}")
