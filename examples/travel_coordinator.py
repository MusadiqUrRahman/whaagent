"""Example: Travel Coordinator Agent with MCP.

This example demonstrates a multi-agent coordinator pattern where multiple
specialist agents work together with MCP server integration.

Usage:
    whaagent run travel-coordinator -i "Plan a 3-day trip to Paris from NYC in June"
"""

from copy import deepcopy
from typing import Any, Dict, List

from langchain_core.messages import BaseMessage

from whaagent import AgentBase, AgentRegistry
from whaagent.interfaces.base import Agent
from whaagent.llm import get_default_model
from whaagent.mcp import MCPProvider


class FlightSpecialistAgent(AgentBase):
    """Flight search specialist agent."""

    @property
    def system_prompt(self) -> str:
        return """You are a flight specialist.
        Prefer tools that provide flight search data (e.g. Kiwi MCP) and return:
        - candidate outbound/return options
        - price, duration, number of stops
        - one recommended flight with rationale
        Keep output short and structured."""


class CityIntelAgent(AgentBase):
    """Destination intelligence specialist agent."""

    @property
    def system_prompt(self) -> str:
        return """You are a destination intelligence specialist.
        Use web retrieval tools (e.g. fetch MCP) to extract practical travel facts:
        - local transport options
        - expected weather in the period requested
        - 3 high-value activities
        - 2 safety/logistics caveats
        Keep output concise and actionable."""


class TravelReviewerAgent(AgentBase):
    """Travel reviewer agent that synthesizes specialist reports."""

    @property
    def system_prompt(self) -> str:
        return """You are a senior travel coordinator.
        You receive analyses from flight and destination specialists.
        Reconcile conflicts, call out assumptions, and produce a final itinerary brief.
        Output sections in this order:
        1) Recommended itinerary
        2) Why this option
        3) Risks / caveats
        4) Next best alternative."""


@AgentRegistry.register(
    "travel-coordinator",
    mcp_servers=["kiwi-com-flight-search", "fetch"],
)
class TravelCoordinatorAgent(Agent):
    """Coordinator example: 3 specialist agents + 2 MCP servers.

    This agent coordinates multiple specialist agents to provide comprehensive
    travel planning with flight search and destination intelligence.
    """

    def __init__(
        self,
        model_name: str = get_default_model(),
        temperature: float = 0.2,
        mcp_provider: MCPProvider | None = None,
        initial_mcp_tools: List[Any] | None = None,
        thread_id: str = "1",
        **kwargs: Any,
    ) -> None:
        shared_kwargs = {
            "model_name": model_name,
            "temperature": temperature,
            "mcp_provider": mcp_provider,
            "initial_mcp_tools": initial_mcp_tools,
            **kwargs,
        }
        self._flight = FlightSpecialistAgent(thread_id=f"{thread_id}:flight", **shared_kwargs)
        self._city = CityIntelAgent(thread_id=f"{thread_id}:city", **shared_kwargs)
        self._reviewer = TravelReviewerAgent(thread_id=f"{thread_id}:review", **shared_kwargs)
        self._specialists = [self._flight, self._city, self._reviewer]

    @staticmethod
    def _stage_config(config: Dict[str, Any] | None, suffix: str) -> Dict[str, Any] | None:
        if config is None:
            return None

        stage_config = deepcopy(config)
        configurable = stage_config.setdefault("configurable", {})
        thread_id = configurable.get("thread_id")
        if isinstance(thread_id, str):
            configurable["thread_id"] = f"{thread_id}:{suffix}"
        return stage_config

    async def run(
        self,
        input_data: str | List[BaseMessage],
        config: Dict[str, Any] | None = None,
    ) -> str:
        if not isinstance(input_data, str):
            raise NotImplementedError("TravelCoordinatorAgent currently supports string input only.")

        flight_report = await self._flight.run(
            f"User request:\n{input_data}\n\nProvide flight recommendations.",
            config=self._stage_config(config, "flight"),
        )
        city_report = await self._city.run(
            "User request:\n"
            f"{input_data}\n\n"
            "Flight specialist report:\n"
            f"{flight_report}\n\n"
            "Now provide destination intelligence that complements the flight options.",
            config=self._stage_config(config, "city"),
        )
        final_brief = await self._reviewer.run(
            "User request:\n"
            f"{input_data}\n\n"
            "Flight specialist report:\n"
            f"{flight_report}\n\n"
            "Destination specialist report:\n"
            f"{city_report}\n\n"
            "Create the final recommendation.",
            config=self._stage_config(config, "review"),
        )
        return str(final_brief)

    def get_tools(self) -> List[Any]:
        all_tools: List[Any] = []
        for specialist in self._specialists:
            all_tools.extend(specialist.get_tools())
        return all_tools
