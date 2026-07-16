"""Tests for the br-news agent."""

from whaagent.agents.br_news import BrNewsAgent


def test_agent_class_exists():
    """Test that the agent class can be imported."""
    assert BrNewsAgent is not None


def test_agent_registered_with_correct_name():
    """Test that the agent is registered as 'br-news' in the registry."""
    from whaagent.registry import AgentRegistry

    assert "br-news" in AgentRegistry._registry
    assert AgentRegistry._registry["br-news"] is BrNewsAgent
