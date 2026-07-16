"""Tests for TenantAgentPool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from whaagent.api.pool import TenantAgentPool


class TestTenantAgentPool:
    """Tests for agent pooling per tenant."""

    def test_pool_starts_empty(self) -> None:
        from whaagent.api.pool import TenantAgentPool

        pool = TenantAgentPool()
        assert len(pool) == 0

    @pytest.mark.asyncio
    async def test_creates_agent_on_first_request(self) -> None:
        from whaagent.api.pool import TenantAgentPool

        pool = TenantAgentPool(max_size=5)
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Hello")

        with patch.object(pool, "_create", return_value=mock_agent) as mock_create:
            agent = await pool.get_or_create(
                tenant_id="primary",
                agent_name="assistant",
                agent_cls=MagicMock(),
                agent_kwargs={},
            )
            assert agent is mock_agent
            assert mock_create.call_count == 1
            assert len(pool) == 1

    @pytest.mark.asyncio
    async def test_reuses_agent_on_second_request(self) -> None:
        from whaagent.api.pool import TenantAgentPool

        pool = TenantAgentPool(max_size=5)
        mock_agent = MagicMock()

        with patch.object(pool, "_create", return_value=mock_agent):
            agent1 = await pool.get_or_create(
                tenant_id="primary",
                agent_name="assistant",
                agent_cls=MagicMock(),
                agent_kwargs={},
            )
            agent2 = await pool.get_or_create(
                tenant_id="primary",
                agent_name="assistant",
                agent_cls=MagicMock(),
                agent_kwargs={},
            )
            assert agent1 is agent2
            assert len(pool) == 1

    @pytest.mark.asyncio
    async def test_separate_tenants_get_separate_agents(self) -> None:
        from whaagent.api.pool import TenantAgentPool

        pool = TenantAgentPool(max_size=5)

        with patch.object(pool, "_create", side_effect=[MagicMock(), MagicMock()]):
            agent1 = await pool.get_or_create(
                tenant_id="tenant-a",
                agent_name="assistant",
                agent_cls=MagicMock(),
                agent_kwargs={},
            )
            agent2 = await pool.get_or_create(
                tenant_id="tenant-b",
                agent_name="assistant",
                agent_cls=MagicMock(),
                agent_kwargs={},
            )
            assert agent1 is not agent2
            assert len(pool) == 2

    @pytest.mark.asyncio
    async def test_evict_removes_oldest_entry(self) -> None:
        from whaagent.api.pool import TenantAgentPool

        pool = TenantAgentPool(max_size=2)
        pool._agents = {
            "tenant-a:assistant": MagicMock(),
            "tenant-b:assistant": MagicMock(),
        }
        pool._access_order = ["tenant-a:assistant", "tenant-b:assistant"]

        await pool._evict_if_needed()

        assert "tenant-a:assistant" not in pool._agents
        assert "tenant-b:assistant" in pool._agents
        assert len(pool) == 1

    @pytest.mark.asyncio
    async def test_evict_calls_cleanup(self) -> None:
        from whaagent.api.pool import TenantAgentPool

        pool = TenantAgentPool(max_size=1)
        mock_old = MagicMock()
        mock_old.cleanup = AsyncMock()
        pool._agents = {"old:assistant": mock_old}
        pool._access_order = ["old:assistant"]

        await pool._evict_if_needed()

        mock_old.cleanup.assert_called_once()


class TestPoolWarmup:
    @pytest.mark.asyncio
    async def test_warmup_creates_agents_for_all_tenants(self) -> None:
        """warmup() should pre-create agents for all specified tenant:agent pairs."""
        pool = TenantAgentPool(max_size=10)

        mock_agent = MagicMock()
        mock_agent._ensure_initialized = AsyncMock()

        mock_cls = MagicMock(return_value=mock_agent)

        configs = [
            {
                "tenant_id": "primary",
                "agent_name": "assistant",
                "agent_cls": mock_cls,
                "agent_kwargs": {"_agent_name": "assistant"},
            },
            {
                "tenant_id": "leticia",
                "agent_name": "assistant",
                "agent_cls": mock_cls,
                "agent_kwargs": {"_agent_name": "assistant"},
            },
        ]

        await pool.warmup(configs)

        assert len(pool) == 2
        assert "primary:assistant" in pool._agents
        assert "leticia:assistant" in pool._agents

    @pytest.mark.asyncio
    async def test_warmup_skips_existing_agents(self):
        """warmup() should not recreate agents already in pool."""
        pool = TenantAgentPool(max_size=10)

        mock_agent = MagicMock()
        mock_agent._ensure_initialized = AsyncMock()

        mock_cls = MagicMock(return_value=mock_agent)

        configs_create = [
            {
                "tenant_id": "primary",
                "agent_name": "assistant",
                "agent_cls": mock_cls,
                "agent_kwargs": {"_agent_name": "assistant"},
            },
        ]
        await pool.warmup(configs_create)
        assert mock_cls.call_count == 1

        await pool.warmup(configs_create)
        assert mock_cls.call_count == 1

    @pytest.mark.asyncio
    async def test_warmup_continues_on_individual_failure(self):
        """warmup() should log failure for one agent but continue with others."""
        pool = TenantAgentPool(max_size=10)

        mock_agent = MagicMock()
        mock_agent._ensure_initialized = AsyncMock()

        fail_cls = MagicMock(side_effect=Exception("MCP connection failed"))
        ok_cls = MagicMock(return_value=mock_agent)

        configs = [
            {
                "tenant_id": "primary",
                "agent_name": "assistant",
                "agent_cls": fail_cls,
                "agent_kwargs": {"_agent_name": "assistant"},
            },
            {
                "tenant_id": "leticia",
                "agent_name": "assistant",
                "agent_cls": ok_cls,
                "agent_kwargs": {"_agent_name": "assistant"},
            },
        ]

        await pool.warmup(configs)

        assert len(pool) == 1
        assert "leticia:assistant" in pool._agents


class TestConnectionValidation:
    @pytest.mark.asyncio
    async def test_validate_connections_detects_stale_agents(self):
        """validate_connections() should detect agents with broken MCP connections."""
        pool = TenantAgentPool(max_size=10)

        # Agent with stale MCP provider
        mock_agent = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get_tools = AsyncMock(side_effect=Exception("no active connection"))
        mock_agent._mcp_provider = mock_provider

        pool._agents["primary:assistant"] = mock_agent
        pool._access_order.append("primary:assistant")

        stale = await pool.validate_connections()

        assert stale == ["primary:assistant"]

    @pytest.mark.asyncio
    async def test_validate_connections_skips_agents_without_mcp(self):
        """validate_connections() should skip agents without MCP providers."""
        pool = TenantAgentPool(max_size=10)

        mock_agent = MagicMock()
        mock_agent._mcp_provider = None

        pool._agents["primary:assistant"] = mock_agent
        pool._access_order.append("primary:assistant")

        stale = await pool.validate_connections()

        assert stale == []

    @pytest.mark.asyncio
    async def test_validate_connections_returns_empty_for_healthy_agents(self):
        """validate_connections() should return empty list when all connections are healthy."""
        pool = TenantAgentPool(max_size=10)

        mock_agent = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get_tools = AsyncMock(return_value=[MagicMock(name="web_search")])
        mock_agent._mcp_provider = mock_provider

        pool._agents["primary:assistant"] = mock_agent
        pool._access_order.append("primary:assistant")

        stale = await pool.validate_connections()

        assert stale == []
