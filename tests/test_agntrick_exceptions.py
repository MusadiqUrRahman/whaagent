"""Tests for whaagent package - exceptions module."""

from whaagent.exceptions import (
    AgentNotFoundError,
    ConfigurationError,
    PromptNotFoundError,
)


def test_whaagent_agent_not_found_error():
    """Test AgentNotFoundError exception."""
    error = AgentNotFoundError("test-agent")
    assert "test-agent" in str(error)
    assert error.name == "test-agent"


def test_whaagent_agent_not_found_with_available():
    """Test AgentNotFoundError with available agents list."""
    error = AgentNotFoundError("test-agent", available=["agent1", "agent2"])
    assert "test-agent" in str(error)
    assert "agent1" in str(error)
    assert "agent2" in str(error)


def test_whaagent_configuration_error():
    """Test ConfigurationError exception."""
    error = ConfigurationError("Invalid configuration")
    assert "Invalid configuration" in str(error)
    assert error.message == "Invalid configuration"


def test_whaagent_configuration_error_with_path():
    """Test ConfigurationError with path."""
    error = ConfigurationError("Invalid configuration", path="/path/to/config.yaml")
    assert "/path/to/config.yaml" in str(error)
    assert error.path == "/path/to/config.yaml"


def test_whaagent_prompt_not_found_error():
    """Test PromptNotFoundError exception."""
    error = PromptNotFoundError("missing-prompt")
    assert "missing-prompt" in str(error)
    assert error.prompt_name == "missing-prompt"


def test_whaagent_prompt_not_found_with_paths():
    """Test PromptNotFoundError with search paths."""
    error = PromptNotFoundError("missing-prompt", search_paths=["/path1", "/path2"])
    assert "missing-prompt" in str(error)
    assert "/path1" in str(error)
    assert error.search_paths == ["/path1", "/path2"]
