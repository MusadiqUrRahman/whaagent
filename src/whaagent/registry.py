import importlib
import logging
import pkgutil
from typing import Callable, Dict, List, Optional, Type

from whaagent.interfaces.base import Agent

# Package to scan for agent modules; imported lazily in discover_agents() to avoid circular
# import (agent modules do "from whaagent.registry import AgentRegistry").
# Must be a package whose __init__.py does NOT import concrete agent modules.
_AGENTS_PACKAGE_NAME = "whaagent.agents"
_logger = logging.getLogger(__name__)


class DuplicateAgentRegistrationError(Exception):
    """Raised when attempting to register an agent with a name that's already in use."""

    def __init__(self, name: str, existing: Type[Agent], new: Type[Agent]):
        self.name = name
        self.existing = existing
        self.new = new
        super().__init__(
            f"Agent '{name}' is already registered with class {existing.__name__}. "
            f"Attempted to register with {new.__name__}."
        )


class _AgentRegistryImplementation:
    """Internal implementation of the agent registry."""

    def __init__(self) -> None:
        self._registry: Dict[str, Type[Agent]] = {}
        self._mcp_servers: Dict[str, Optional[List[str]]] = {}
        self._tool_categories: Dict[str, Optional[List[str]]] = {}
        self._strict_registration: bool = False

    def set_strict_registration(self, strict: bool = True) -> None:
        """Set whether duplicate registrations should raise an error."""
        self._strict_registration = strict

    def register(
        self,
        name: str,
        mcp_servers: Optional[List[str]] = None,
        *,
        tool_categories: Optional[List[str]] = None,
        override: bool = False,
    ) -> Callable[[Type[Agent]], Type[Agent]]:
        """Decorator to register an agent class with its MCP servers and tool categories.

        Args:
            name: Agent identifier.
            mcp_servers: List of MCP server names this agent can use.
            tool_categories: List of tool categories to document in system prompt (e.g., ["web", "git"]).
            override: Whether to override existing registration.

        Returns:
            Decorator function.
        """

        def decorator(agent_cls: Type[Agent]) -> Type[Agent]:
            if name in self._registry and not override:
                existing_cls = self._registry[name]
                if self._strict_registration:
                    raise DuplicateAgentRegistrationError(name, existing_cls, agent_cls)
                _logger.warning(
                    "Duplicate agent registration: '%s' already registered with %s, overwriting with %s",
                    name,
                    existing_cls.__name__,
                    agent_cls.__name__,
                )
            self._registry[name] = agent_cls
            self._mcp_servers[name] = mcp_servers
            self._tool_categories[name] = tool_categories
            _logger.debug("Registered agent '%s' with class %s", name, agent_cls.__name__)
            return agent_cls

        return decorator

    def get(self, name: str) -> Optional[Type[Agent]]:
        """Get an agent class by name."""
        return self._registry.get(name)

    def get_mcp_servers(self, name: str) -> Optional[List[str]]:
        """Return the list of MCP server names this agent is allowed to use."""
        return self._mcp_servers.get(name)

    def get_tool_categories(self, name: str) -> Optional[List[str]]:
        """Return the list of tool categories to document for this agent."""
        return self._tool_categories.get(name)

    def list_agents(self) -> list[str]:
        """List all registered agent names."""
        return list(self._registry.keys())

    def discover_agents(self) -> None:
        """Import all modules in the agents package so decorators run."""
        try:
            agents_pkg = importlib.import_module(_AGENTS_PACKAGE_NAME)
            prefix = agents_pkg.__name__ + "."
            for modinfo in pkgutil.iter_modules(agents_pkg.__path__, prefix):
                importlib.import_module(modinfo.name)
        except Exception as e:
            _logger.error("Failed to discover agents: %s", e)

    def clear(self) -> None:
        """Clear all registered agents and their configurations."""
        self._registry.clear()
        self._mcp_servers.clear()
        self._tool_categories.clear()


# Export a singleton instance. Using the same name as the original class
# ensures that @AgentRegistry.register and AgentRegistry.get keep working.
AgentRegistry = _AgentRegistryImplementation()
