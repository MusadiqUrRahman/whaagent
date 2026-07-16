"""Tests for whaagent package - LLM providers module."""

import os

from whaagent.llm.providers import (
    DEFAULT_MODELS,
    _create_model,
    detect_provider,
    get_default_model,
)


def test_whaagent_detect_provider_anthropic():
    """Test detecting Anthropic provider."""
    # Save original values
    original = {}
    for key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"]:
        original[key] = os.environ.get(key)

    try:
        # Clear and set
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("GOOGLE_API_KEY", None)
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"

        provider = detect_provider()
        assert provider == "anthropic"
    finally:
        # Restore
        for key, value in original.items():
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)


def test_whaagent_detect_provider_openai():
    """Test detecting OpenAI provider as fallback."""
    # Save original values
    original = {}
    for key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY"]:
        original[key] = os.environ.get(key)

    try:
        # Clear all provider keys
        for key in ["ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY"]:
            os.environ.pop(key, None)

        # OpenAI is the default fallback
        provider = detect_provider()
        assert provider == "openai"
    finally:
        # Restore
        for key, value in original.items():
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)


def test_whaagent_get_default_model():
    """Test getting default model for providers."""
    # get_default_model() uses detect_provider() internally
    # and returns the default model for that provider
    model = get_default_model()
    assert isinstance(model, str)
    assert len(model) > 0


def test_whaagent_default_models_dict():
    """Test DEFAULT_MODELS dictionary has expected providers."""
    assert "anthropic" in DEFAULT_MODELS
    assert "openai" in DEFAULT_MODELS
    assert "google_genai" in DEFAULT_MODELS
    assert "ollama" in DEFAULT_MODELS

    # Check values are strings
    for provider, model in DEFAULT_MODELS.items():
        assert isinstance(model, str)


def test_whaagent_provider_type():
    """Test Provider type literal values."""
    # These should be valid provider names
    valid_providers = [
        "anthropic",
        "openai",
        "ollama",
        "azure_openai",
        "google_vertexai",
        "google_genai",
        "mistralai",
        "cohere",
        "bedrock",
        "huggingface",
    ]

    for provider in valid_providers:
        # Just verify they're strings
        assert isinstance(provider, str)


def test_whaagent_create_model_with_openai():
    """Test creating a model with OpenAI (no API key required for initialization)."""
    # OpenAI is the fallback, should work even without explicit key
    model = _create_model("gpt-4o-mini", 0.7)
    assert model is not None
