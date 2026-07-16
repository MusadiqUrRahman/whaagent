"""FastAPI application factory and server."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from whaagent.api.middleware import RequestLoggingAndErrorMiddleware
from whaagent.api.routes import agents, health, whatsapp
from whaagent.config import get_config
from whaagent.tools.deep_scrape import DeepScrapeTool

logger = logging.getLogger(__name__)


async def _check_mcp_health(app: FastAPI) -> None:
    """Periodically check MCP health and evict unhealthy agents.

    Checks toolbox /api/manifest endpoint every 60 seconds. If unhealthy,
    evicts all agents from pool to force fresh connections on next request.
    """
    import httpx

    config = get_config()
    toolbox_url = config.mcp.toolbox_url or "http://localhost:8080"
    pool = app.state.agent_pool

    while True:
        await asyncio.sleep(60)  # Check every 60s
        try:
            async with httpx.AsyncClient() as client:
                # Toolbox /api/manifest returns JSON immediately (used for health check)
                resp = await client.get(f"{toolbox_url}/api/manifest", timeout=5)
                if resp.status_code != 200:
                    logger.warning("Toolbox health check failed (status=%s), evicting all agents", resp.status_code)
                    for key in list(pool._agents.keys()):
                        tenant_id, agent_name = key.split(":", 1)
                        await pool.evict(tenant_id, agent_name)
        except Exception as e:
            logger.warning(f"MCP health check failed: {e}, evicting all agents")
            for key in list(pool._agents.keys()):
                tenant_id, agent_name = key.split(":", 1)
                await pool.evict(tenant_id, agent_name)


async def _keep_alive_pool(app: FastAPI) -> None:
    """Periodically validate pooled agent connections and refresh stale ones.

    Runs every 5 minutes. Detects stale MCP connections before user requests
    hit them, preventing the 40s eviction+recreation penalty.
    """
    pool = app.state.agent_pool
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        try:
            stale = await pool.validate_connections()
            for key in stale:
                tenant_id, agent_name = key.split(":", 1)
                logger.info("[keep-alive] evicting stale agent: %s", key)
                await pool.evict(tenant_id, agent_name)
        except Exception as e:
            logger.warning("[keep-alive] error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    from whaagent.logging_config import setup_logging

    config = get_config()
    setup_logging(config)
    logger.info("Starting whaagent API server on %s:%s", config.api.host, config.api.port)
    from whaagent.llm.providers import detect_provider, get_default_model

    provider = detect_provider()
    model = get_default_model()
    logger.info("LLM: provider=%s model=%s", provider, model)

    from whaagent.api.pool import TenantAgentPool
    from whaagent.registry import AgentRegistry
    from whaagent.storage.tenant_manager import TenantManager

    app.state.tenant_manager = TenantManager(base_path=config.storage.base_path)

    # Discover agents and initialize pool
    AgentRegistry.discover_agents()
    app.state.agent_pool = TenantAgentPool(max_size=10)
    logger.info("Agent pool initialized (max_size=10)")

    # Pre-warm agent pool for all configured tenants
    if config.whatsapp.tenants:
        warmup_configs: list[dict[str, Any]] = []
        for tenant in config.whatsapp.tenants:
            if not tenant.id:
                continue
            agent_name = tenant.default_agent
            agent_cls = AgentRegistry.get(agent_name)
            if not agent_cls:
                logger.warning("Skipping warmup for unknown agent '%s'", agent_name)
                continue

            allowed_mcp = AgentRegistry.get_mcp_servers(agent_name)
            tool_categories = AgentRegistry.get_tool_categories(agent_name)

            thread_id = f"whatsapp:{tenant.id}:warmup"
            tenant_db = app.state.tenant_manager.get_database(tenant.id)

            agent_kwargs: dict[str, Any] = dict(
                _agent_name=agent_name,
                tool_categories=tool_categories,
                model_name=config.llm.model,
                temperature=config.llm.temperature,
                thread_id=thread_id,
                db_path=str(tenant_db._db_path),
                progress_callback=None,
            )

            if allowed_mcp:
                agent_kwargs["mcp_server_names"] = allowed_mcp

            warmup_configs.append(
                {
                    "tenant_id": tenant.id,
                    "agent_name": agent_name,
                    "agent_cls": agent_cls,
                    "agent_kwargs": agent_kwargs,
                }
            )

        if warmup_configs:
            logger.info("Warming up %s agent(s) for %s tenant(s)...", len(warmup_configs), len(config.whatsapp.tenants))
            try:
                await app.state.agent_pool.warmup(warmup_configs)
                logger.info("Agent pool warmup complete (pool_size=%s)", len(app.state.agent_pool))
            except Exception as e:
                logger.warning("Agent pool warmup failed (agents will be created on first request): %s", e)

    # Warm up Playwright browser for DeepScrapeTool (skip when PLAYWRIGHT_PERSISTENT=false)
    if DeepScrapeTool.is_persistent():
        try:
            await DeepScrapeTool.warmup()
            logger.info("Playwright browser warmed up successfully")
        except Exception as e:
            logger.warning("Failed to warm up Playwright browser: %s", e)
    else:
        logger.info("Playwright browser warmup skipped (PLAYWRIGHT_PERSISTENT=false)")

    # Start MCP health check task
    app.state._health_task = asyncio.create_task(_check_mcp_health(app))
    logger.info("MCP health check task started")

    # Start pool keep-alive task
    app.state._keep_alive_task = asyncio.create_task(_keep_alive_pool(app))
    logger.info("Pool keep-alive task started")

    yield

    # Cancel MCP health check task
    if hasattr(app.state, "_health_task"):
        app.state._health_task.cancel()
        logger.info("MCP health check task cancelled")

    # Cancel pool keep-alive task
    if hasattr(app.state, "_keep_alive_task"):
        app.state._keep_alive_task.cancel()
        logger.info("Pool keep-alive task cancelled")

    # Clean up SSE connections
    from whaagent.api.routes.whatsapp import sse_queues

    for tenant_id, queues in sse_queues.items():
        for queue in queues:
            await queue.put({"type": "shutdown", "data": "{}"})
    sse_queues.clear()

    # Evict all pooled agents
    pool = getattr(app.state, "agent_pool", None)
    if pool:
        for key in list(pool._agents.keys()):
            tenant_id, agent_name = key.split(":", 1)
            await pool.evict(tenant_id, agent_name)

    app.state.tenant_manager.close_all()

    # Clean up Playwright browser
    await DeepScrapeTool.shutdown()
    logger.info("Playwright browser shut down")

    logger.info("Shutting down whaagent API server")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="whaagent API",
        description="Production-grade API for AI agents",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register error handling and logging middleware
    app.add_middleware(RequestLoggingAndErrorMiddleware)

    app.include_router(health.router, tags=["health"])
    app.include_router(agents.router, tags=["agents"])
    app.include_router(whatsapp.router, prefix="/api/v1/whatsapp", tags=["whatsapp"])
    app.include_router(whatsapp.channels_router, prefix="/api/v1/channels", tags=["channels"])
    return app


def run_server() -> None:
    """Run the API server."""
    import uvicorn

    config = get_config()

    uvicorn.run(
        "whaagent.api.server:create_app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.debug,
        factory=True,
        timeout_graceful_shutdown=5,
    )
