"""Tests for the Recipe agent."""

from whaagent.agents.recipe import RecipeAgent


def test_agent_class_exists():
    """Test that the agent class can be imported."""
    assert RecipeAgent is not None


def test_agent_registered_with_correct_name():
    """Test that the agent is registered as 'recipe' in the registry."""
    from whaagent.registry import AgentRegistry

    assert "recipe" in AgentRegistry._registry
    assert AgentRegistry._registry["recipe"] is RecipeAgent


def test_system_prompt_loaded():
    """System prompt should load from recipe.md."""
    agent = RecipeAgent.__new__(RecipeAgent)
    prompt = agent.system_prompt
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "ingredient" in prompt.lower()


def test_local_tools_empty():
    """Recipe agent should have no local tools (uses MCP only)."""
    agent = RecipeAgent.__new__(RecipeAgent)
    assert agent.local_tools() == []
