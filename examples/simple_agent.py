"""Example: Simple Agent without MCP.

This example demonstrates a minimal agent implementation using the whaagent
library without any MCP server integration.

Usage:
    whaagent run simple -i "What is the capital of France?"
"""

from typing import Any, Dict, List, Union

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate

from whaagent import AgentRegistry
from whaagent.interfaces.base import Agent
from whaagent.llm import _create_model, get_default_model


@AgentRegistry.register("simple", mcp_servers=None)
class SimpleAgent(Agent):
    """A simple agent implementation using LangChain.

    No MCP access (mcp_servers=None in registry).
    """

    def __init__(self, model_name: str | None = None, temperature: float = 0.0, **kwargs: Any) -> None:
        if model_name is None:
            model_name = get_default_model()
        self.model = _create_model(model_name, temperature)
        self.prompt = ChatPromptTemplate.from_messages(
            [("system", "You are a helpful assistant."), ("user", "{input}")]
        )
        self.chain = self.prompt | self.model

    async def run(
        self,
        input_data: Union[str, List[BaseMessage]],
        config: Dict[str, Any] | None = None,
    ) -> Union[str, BaseMessage]:
        """Run the agent with the given input string."""
        if isinstance(input_data, str):
            response = await self.chain.ainvoke({"input": input_data})
            return str(response.content)

        raise NotImplementedError("SimpleAgent currently only supports string input.")

    def get_tools(self) -> List[Any]:
        return []
