"""Tests for the es-news agent."""

from whaagent.agents.es_news import EsNewsAgent


def test_agent_class_exists():
    """Test that the agent class can be imported."""
    assert EsNewsAgent is not None


def test_agent_registered_with_correct_name():
    """Test that the agent is registered as 'es-news' in the registry."""
    from whaagent.registry import AgentRegistry

    assert "es-news" in AgentRegistry._registry
    assert AgentRegistry._registry["es-news"] is EsNewsAgent
