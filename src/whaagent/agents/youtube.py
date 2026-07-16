"""YouTube video analysis agent with transcript extraction capabilities."""

import logging
from typing import Any, Sequence

from langchain_core.tools import StructuredTool

from whaagent.agent import AgentBase
from whaagent.prompts import load_prompt
from whaagent.registry import AgentRegistry
from whaagent.tools.youtube_transcript import YouTubeTranscriptTool

logger = logging.getLogger(__name__)


@AgentRegistry.register("youtube", mcp_servers=["toolbox"])
class YouTubeAgent(AgentBase):
    """YouTube video analysis agent.

    This agent specializes in extracting insights from YouTube videos
    through transcript analysis. It can summarize content, answer
    questions about specific topics, and provide timestamp references.

    Capabilities:
        - Extract and analyze video transcripts
        - Summarize video content concisely
        - Answer questions about specific parts
        - Identify key points with timestamps
        - Compare multiple videos
        - Extract quotes and citations

    Example Usage:
        bin/agent.sh youtube -i "Summarize https://youtube.com/watch?v=abc123"
        bin/agent.sh youtube -i "What does this video say about AI? https://..."
    """

    @property
    def system_prompt(self) -> str:
        """Return the system prompt for this agent.

        The system prompt defines the agent's behavior and capabilities.
        """
        return load_prompt("youtube")

    def local_tools(self) -> Sequence[Any]:
        """Return YouTube-specific tools.

        Returns:
            A sequence of tools available to the agent.
        """
        tool = YouTubeTranscriptTool()
        return [
            StructuredTool.from_function(
                func=tool.invoke,
                name=tool.name,
                description=tool.description,
            )
        ]
