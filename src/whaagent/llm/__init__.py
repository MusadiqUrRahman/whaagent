"""LLM provider detection and model creation.

This module provides utilities for detecting available LLM providers
and creating appropriate model instances.
"""

from whaagent.llm.local_reasoning import (
    LocalReasoningLLM,
    get_local_developer_model,
)
from whaagent.llm.providers import (
    DEFAULT_MODELS,
    Provider,
    _create_model,
    detect_provider,
    get_default_model,
)

__all__ = [
    "DEFAULT_MODELS",
    "Provider",
    "_create_model",
    "detect_provider",
    "get_default_model",
    "LocalReasoningLLM",
    "get_local_developer_model",
]
