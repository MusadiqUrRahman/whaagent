"""whaagent: An AI agent framework for building AI-powered applications.

This library provides a flexible framework for creating agents with tool
integration, MCP (Model Context Protocol) support, and LLM provider
abstraction.

Example usage:
    ```python
    from whaagent import AgentRegistry

    # Discover all available agents
    AgentRegistry.discover_agents()

    # List available agents
    for agent_name in AgentRegistry.list_agents():
        print(agent_name)

    # Get an agent class
    AgentClass = AgentRegistry.get("developer")

    # Create and run the agent
    agent = AgentClass()
    response = await agent.run("Explain this codebase")
    ```

CLI usage:
    ```bash
    # List all available agents
    whaagent list

    # Run an agent with input
    whaagent run developer -i "Explain this codebase"

    # Get information about an agent
    whaagent info developer

    # Show current configuration
    whaagent config
    ```

## Public API

### Core Classes
- AgentBase: Base class for creating agents
- AgentRegistry: Agent discovery and registration

### Configuration
- get_config(): Get the current configuration
- whaagentConfig: Main configuration class

### LLM
- detect_provider(): Detect the LLM provider to use
- get_default_model(): Get the default model name
- Provider: Literal type for LLM providers

### Exceptions
- AgentNotFoundError: Raised when an agent is not found
- ConfigurationError: Raised when configuration is invalid
- PromptNotFoundError: Raised when a prompt file is not found
"""

from whaagent.agent import AgentBase
from whaagent.agents import (
    DeveloperAgent,
    GithubPrReviewerAgent,
    LearningAgent,
    NewsAgent,
    YouTubeAgent,
)
from whaagent.config import whaagentConfig, get_config
from whaagent.exceptions import (
    AgentNotFoundError,
    ConfigurationError,
    PromptNotFoundError,
)
from whaagent.llm import Provider, _create_model, detect_provider, get_default_model
from whaagent.registry import AgentRegistry

try:
    from importlib.metadata import version as _get_version

    __version__ = _get_version("whaagent")
except Exception:
    __version__ = "0.0.0"

__all__ = [
    # Core
    "AgentBase",
    "AgentRegistry",
    # Agents
    "DeveloperAgent",
    "GithubPrReviewerAgent",
    "LearningAgent",
    "NewsAgent",
    "YouTubeAgent",
    # Configuration
    "whaagentConfig",
    "get_config",
    # LLM
    "Provider",
    "_create_model",
    "detect_provider",
    "get_default_model",
    # Exceptions
    "AgentNotFoundError",
    "ConfigurationError",
    "PromptNotFoundError",
    # Version
    "__version__",
]
