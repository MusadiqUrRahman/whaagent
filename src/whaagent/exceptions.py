"""Custom exceptions for whaagent."""


class whaagentError(Exception):
    """Base exception for all whaagent errors."""


class AgentNotFoundError(whaagentError):
    """Raised when an agent with the given name is not found.

    Args:
        name: The name of the agent that was not found.
        available: Optional list of available agent names.
    """

    def __init__(self, name: str, available: list[str] | None = None) -> None:
        self.name = name
        self.available = available or []

        msg = f"Agent '{name}' not found."

        if self.available:
            msg += f" Available agents: {', '.join(sorted(self.available))}"

        super().__init__(msg)


class ConfigurationError(whaagentError):
    """Raised when there's an error in the configuration.

    Args:
        message: Description of the configuration error.
        path: Optional path to the configuration file that caused the error.
    """

    def __init__(self, message: str, path: str | None = None) -> None:
        self.message = message
        self.path = path

        msg = message
        if path:
            msg = f"Configuration error in '{path}': {message}"

        super().__init__(msg)


class PromptNotFoundError(whaagentError):
    """Raised when a prompt file cannot be found.

    Args:
        prompt_name: The name of the prompt that was not found.
        search_paths: Optional list of paths that were searched.
    """

    def __init__(self, prompt_name: str, search_paths: list[str] | None = None) -> None:
        self.prompt_name = prompt_name
        self.search_paths = search_paths or []

        msg = f"Prompt '{prompt_name}' not found."

        if self.search_paths:
            msg += f" Searched: {', '.join(self.search_paths)}"

        super().__init__(msg)
