from typing import Any, Sequence

from whaagent.agent import AgentBase
from whaagent.prompts import load_prompt
from whaagent.registry import AgentRegistry


@AgentRegistry.register("br-news", mcp_servers=["toolbox"], tool_categories=["web"])
class BrNewsAgent(AgentBase):
    """Brazilian news agent that fetches, summarizes, and fact-checks news from top BR portals."""

    @property
    def system_prompt(self) -> str:
        return load_prompt("br-news")

    def local_tools(self) -> Sequence[Any]:
        return []
