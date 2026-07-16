"""Agent execution endpoints for the whaagent API."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from whaagent.api.auth import verify_api_key
from whaagent.api.deps import TenantDB, TenantId
from whaagent.config import get_config
from whaagent.logging_config import TenantLogAdapter
from whaagent.registry import AgentRegistry


class AgentRunRequest(BaseModel):
    """Request model for running an agent."""

    input: str
    thread_id: str | None = None


class AgentRunResponse(BaseModel):
    """Response model for agent execution."""

    output: str
    agent: str


router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/api/v1/agents")
async def list_agents() -> list[str]:
    """List all available agents.

    Returns:
        A list of agent names that are registered.
    """
    AgentRegistry.discover_agents()
    return AgentRegistry.list_agents()


@router.post("/api/v1/agents/{agent_name}/run")
async def run_agent(
    agent_name: str,
    request: AgentRunRequest,
    tenant_id: TenantId,
    database: TenantDB,
) -> AgentRunResponse:
    """Run an agent with tenant-scoped checkpointer.

    Args:
        agent_name: Name of the agent to run.
        request: The agent run request containing input and thread_id.
        tenant_id: The tenant ID from API key verification.
        database: The tenant-scoped database for persistence.

    Returns:
        The agent's response.

    Raises:
        HTTPException: If agent is not found or fails to execute.
    """
    # Get logger with tenant context
    logger = TenantLogAdapter(logging.getLogger(__name__), tenant_id)
    logger.info("Starting agent execution: %s for tenant: %s", agent_name, tenant_id)

    # Discover and get the agent class
    AgentRegistry.discover_agents()
    agent_cls = AgentRegistry.get(agent_name)

    if not agent_cls:
        logger.error("Agent not found: %s", agent_name)
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")

    # Get model configuration
    config = get_config()
    model_name = config.llm.model
    temperature = config.llm.temperature
    logger.info("Agent configuration - model: %s, temperature: %.2f", model_name, temperature)

    # Prepare agent constructor arguments
    constructor_args = {
        "model_name": model_name,
        "temperature": temperature,
        "thread_id": request.thread_id or "1",
    }

    # Add checkpointer if thread_id is provided (for persistent memory)
    if request.thread_id:
        constructor_args["checkpointer"] = database.get_checkpointer(is_async=True)
        logger.info("Using checkpointer for thread_id: %s", request.thread_id)

    # Create and run the agent
    try:
        agent = agent_cls(**constructor_args)
        result = await agent.run(request.input)
        # Ensure result is a string
        output = str(result) if result is not None else ""

        logger.info("Agent execution completed successfully for tenant: %s", tenant_id)
        return AgentRunResponse(
            output=output,
            agent=agent_name,
        )
    except Exception as e:
        logger.error("Agent execution failed for tenant %s: %s", tenant_id, str(e))
        raise HTTPException(status_code=500, detail="Agent execution failed")
