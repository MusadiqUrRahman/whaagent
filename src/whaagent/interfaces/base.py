from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from langchain_core.messages import BaseMessage
from langchain_core.tools import StructuredTool


class Agent(ABC):
    """Abstract Base Class for an Agent."""

    @abstractmethod
    async def run(
        self,
        input_data: Union[str, List[BaseMessage]],
        config: Optional[Dict[str, Any]] = None,
    ) -> Union[str, BaseMessage]:
        """Run agent with given input."""
        pass

    @abstractmethod
    def get_tools(self) -> List[Any]:
        """Return available tools for this agent."""
        pass


class Tool(ABC):
    """Abstract Base Class for a Tool."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of tool."""

    @property
    @abstractmethod
    def description(self) -> str:
        """A description of what tool does."""

    @abstractmethod
    def invoke(self, input_str: str) -> Any:
        """Execute tool logic."""
        pass

    def to_langchain_tool(self) -> StructuredTool:
        """Convert to a LangChain StructuredTool."""
        return StructuredTool.from_function(
            func=self.invoke,
            name=self.name,
            description=self.description,
        )

    @classmethod
    def from_function(
        cls,
        func: Any,
        name: str,
        description: str,
    ) -> StructuredTool:
        """Create a LangChain StructuredTool from a plain function.

        This factory method provides a single point of access to LangChain
        tool creation, decoupling agent code from direct StructuredTool imports.

        Args:
            func: The callable to wrap as a tool.
            name: Tool name (used by LLM to identify the tool).
            description: Tool description (used by LLM to understand the tool).

        Returns:
            A LangChain StructuredTool wrapping the function.
        """
        return StructuredTool.from_function(func=func, name=name, description=description)
