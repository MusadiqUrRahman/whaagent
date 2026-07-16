from pathlib import Path
from typing import Any, Sequence

from whaagent.agent import AgentBase
from whaagent.prompts import load_prompt
from whaagent.registry import AgentRegistry
from whaagent.tools import (
    CodeSearcher,
    FileEditorTool,
    FileFinderTool,
    FileFragmentReaderTool,
    FileOutlinerTool,
    StructureExplorerTool,
)


@AgentRegistry.register("developer", mcp_servers=["toolbox"])
class DeveloperAgent(AgentBase):
    """
    A specialized agent for codebase exploration and development.
    Equipped with tools to search, structure, and read code, plus MCP capabilities.
    """

    @property
    def system_prompt(self) -> str:
        return load_prompt("developer")

    def local_tools(self) -> Sequence[Any]:
        # Initialize tool instances with current working directory
        searcher = CodeSearcher(str(Path.cwd()))
        finder = FileFinderTool(str(Path.cwd()))
        explorer = StructureExplorerTool(str(Path.cwd()))
        outliner = FileOutlinerTool(str(Path.cwd()))
        reader = FileFragmentReaderTool(str(Path.cwd()))
        editor = FileEditorTool(str(Path.cwd()))

        tools = [
            searcher,
            finder,
            explorer,
            outliner,
            reader,
            editor,
        ]
        return [t.to_langchain_tool() for t in tools]
