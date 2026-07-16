"""CommitterAgent for analyzing git changes and generating commit messages."""

from typing import Any, Sequence

from whaagent.agent import AgentBase
from whaagent.prompts import load_prompt
from whaagent.registry import AgentRegistry
from whaagent.tools.git_command import GitCommandTool


@AgentRegistry.register("committer")
class CommitterAgent(AgentBase):
    """Agent specialized in git operations and commit message generation."""

    @property
    def system_prompt(self) -> str:
        return load_prompt("committer")

    def local_tools(self) -> Sequence[Any]:
        # Tool defaults to current directory
        return [GitCommandTool().to_langchain_tool()]
