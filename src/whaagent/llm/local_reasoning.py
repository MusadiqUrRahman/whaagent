"""Local Reasoning LLM provider for whaagent.

This module provides a custom ChatOpenAI subclass that strips
<reasoning> tags from model responses, useful for local models
that output thinking tokens.
"""

import re
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.outputs import ChatResult
from langchain_openai import ChatOpenAI
from pydantic import SecretStr


class LocalReasoningLLM(ChatOpenAI):
    """Custom provider for whaagent to handle local reasoning models.

    This class extends ChatOpenAI to automatically strip <reasoning>
    tags from model responses. Local reasoning models often output their
    reasoning process in tags that should be hidden from the agent.

    Example:
        >>> model = LocalReasoningLLM(
        ...     openai_api_base="http://localhost:8080/v1",
        ...     model="glm-4.7-flash",
        ... )
        >>> response = model.invoke("Hello")
        # Any <reasoning>...</reasoning> tags are stripped from response
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize LocalReasoningLLM with parent configuration."""
        super().__init__(*args, **kwargs)

    def _generate(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: object,
    ) -> ChatResult:
        """Generate chat completion, stripping reasoning tags from output.

        Args:
            messages: Input messages for the model.
            stop: Optional stop sequences.
            run_manager: Optional callback manager.
            **kwargs: Additional keyword arguments.

        Returns:
            A ChatResult with <reasoning> tags stripped from message content.
        """
        result = super()._generate(messages, stop, run_manager, **kwargs)

        # Strip <reasoning> tags from all generations
        for generation in result.generations:
            if hasattr(generation.message, "content") and isinstance(generation.message.content, str):
                generation.message.content = re.sub(
                    r"<reasoning>.*?</reasoning>",
                    "",
                    generation.message.content,
                    flags=re.DOTALL,
                ).strip()

        return result


def get_local_developer_model() -> LocalReasoningLLM:
    """Factory function to create a LocalReasoningLLM for development.

    Returns:
        A LocalReasoningLLM configured for local development use with
        low temperature for consistent tool calling.

    Example:
        >>> model = get_local_developer_model()
        >>> response = model.invoke("Write Python code")
    """
    return LocalReasoningLLM(
        openai_api_base="http://localhost:8080/v1",
        api_key=SecretStr("not-needed"),
        model="glm-4.7-flash",
        temperature=0.2,  # Low for consistent tool calling
    )
