"""Tests for Tool ABC factory method."""


def test_tool_from_function_creates_structured_tool() -> None:
    """Tool.from_function() should create a LangChain StructuredTool."""
    from langchain_core.tools import StructuredTool

    from whaagent.interfaces.base import Tool

    def my_func(x: str) -> str:
        return f"result: {x}"

    tool = Tool.from_function(func=my_func, name="my_func", description="A test function")

    assert isinstance(tool, StructuredTool)
    assert tool.name == "my_func"
    assert tool.description == "A test function"


def test_tool_from_function_is_callable() -> None:
    """Tool created via from_function should be invokable."""
    from whaagent.interfaces.base import Tool

    def echo(text: str) -> str:
        return text

    tool = Tool.from_function(func=echo, name="echo", description="Echo tool")
    result = tool.invoke({"text": "hello"})
    assert result == "hello"


def test_github_pr_reviewer_tools_accessible_via_tool_factory() -> None:
    """GithubPrReviewerAgent tools should be accessible via Tool.from_function."""
    from langchain_core.tools import StructuredTool

    from whaagent.agents.github_pr_reviewer import GithubPrReviewerAgent

    agent = GithubPrReviewerAgent()
    tools = agent.local_tools()

    assert len(tools) == 6
    # All tools should be StructuredTool instances (created via Tool.from_function)
    for tool in tools:
        assert isinstance(tool, StructuredTool)
        assert tool.name is not None
        assert tool.description is not None
