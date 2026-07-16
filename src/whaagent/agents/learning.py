"""Learning/Tutorial agent for creating step-by-step educational content.

This module provides an agent specialized in creating tutorials,
explaining concepts, and providing educational content with web research.
"""

from typing import Any, Sequence

from whaagent.agent import AgentBase
from whaagent.prompts import load_prompt
from whaagent.registry import AgentRegistry


@AgentRegistry.register("learning", mcp_servers=["toolbox"])
class LearningAgent(AgentBase):
    """Agent specialized in creating tutorials and educational content.

    This agent uses toolbox MCP tools for web research and content fetching
    to create comprehensive, step-by-step tutorials.

    Capabilities:
    - Creates structured tutorials with clear steps
    - Explains complex concepts in simple terms
    - Provides examples and code snippets
    - Researches current best practices via toolbox tools
    """

    @property
    def system_prompt(self) -> str:
        """System prompt for the learning agent."""
        return load_prompt("learning")

    def local_tools(self) -> Sequence[Any]:
        """Learning agent uses only MCP tools for web research."""
        return []
