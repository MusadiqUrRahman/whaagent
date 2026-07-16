"""Recipe agent for suggesting recipes based on available ingredients.

This module provides an agent specialized in suggesting practical,
doable recipes given a list of ingredients the user has at home.
"""

from typing import Any, Sequence

from whaagent.agent import AgentBase
from whaagent.prompts import load_prompt
from whaagent.registry import AgentRegistry


@AgentRegistry.register("recipe", mcp_servers=["toolbox"])
class RecipeAgent(AgentBase):
    """Agent specialized in suggesting recipes from available ingredients.

    Capabilities:
    - Suggests recipes based on ingredients the user has at home
    - Prioritizes simple, practical recipes with few extra purchases
    - Adapts to dietary restrictions and cuisine preferences
    - Uses web search to find recipes when needed
    """

    @property
    def system_prompt(self) -> str:
        """System prompt for the recipe agent."""
        return load_prompt("recipe")

    def local_tools(self) -> Sequence[Any]:
        """Recipe agent uses only MCP tools for web search."""
        return []
