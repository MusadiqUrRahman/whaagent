"""Example: Chef Agent with MCP web search capabilities.

This example demonstrates how to create a custom agent using the whaagent
library with MCP server integration for web search.

Usage:
    whaagent run chef -i "I have eggs, cheese, and bread"
"""

from whaagent import AgentBase, AgentRegistry


@AgentRegistry.register("chef", mcp_servers=["fetch"])
class ChefAgent(AgentBase):
    """A recipe-focused agent with MCP web search capabilities."""

    @property
    def system_prompt(self) -> str:
        return """You are a personal chef.
        The user will give you a list of ingredients they have left over in their house.
        Using the web search tool (web_fetch_search), search the web for recipes
        that can be made with the ingredients they have.
        Return recipe suggestions and eventually the recipe instructions
        to the user, if requested."""
