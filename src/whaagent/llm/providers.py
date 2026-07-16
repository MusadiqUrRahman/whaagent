"""LLM provider detection and model creation utilities."""

import logging
import os
import threading
from typing import Any, Callable, Literal

from dotenv import load_dotenv
from pydantic import SecretStr

load_dotenv()  # Load .env before reading environment variables

logger = logging.getLogger(__name__)

Provider = Literal[
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

# Default models for each provider
DEFAULT_MODELS: dict[Provider, str] = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "ollama": "llama3.2",
    "azure_openai": "gpt-4o-mini",
    "google_vertexai": "gemini-2.0-flash-exp",
    "google_genai": "gemini-2.0-flash-exp",
    "mistralai": "mistral-large-latest",
    "cohere": "command-r-plus",
    "bedrock": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "huggingface": "meta-llama/Llama-3.2-3B-Instruct",
}


def detect_provider() -> Provider:
    """Detect which LLM provider to use based on available API keys.

    Returns:
        The detected provider name. Priority order:
        1. anthropic (ANTHROPIC_API_KEY)
        2. google_vertexai (GOOGLE_VERTEX_PROJECT_ID or GOOGLE_VERTEX_CREDENTIALS)
        3. google_genai (GOOGLE_API_KEY)
        4. azure_openai (AZURE_OPENAI_API_KEY)
        5. mistralai (MISTRAL_API_KEY)
        6. cohere (COHERE_API_KEY)
        7. bedrock (AWS_PROFILE or AWS_ACCESS_KEY_ID)
        8. huggingface (HUGGINGFACEHUB_API_TOKEN)
        9. ollama (OLLAMA_BASE_URL or localhost:11434)
        10. openai (OPENAI_API_KEY)
        11. openai (fallback)

    Note:
        Ollama is special as it runs locally without an API key.
        It's checked via OLLAMA_BASE_URL environment variable.

        Groq is reserved for audio transcription only (GROQ_AUDIO_API_KEY).
        It is NOT used as an LLM provider.
    """
    # Check in order of priority
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("GOOGLE_VERTEX_PROJECT_ID") or os.getenv("GOOGLE_VERTEX_CREDENTIALS"):
        return "google_vertexai"
    if os.getenv("GOOGLE_API_KEY"):
        return "google_genai"
    if os.getenv("AZURE_OPENAI_API_KEY"):
        return "azure_openai"
    if os.getenv("MISTRAL_API_KEY"):
        return "mistralai"
    if os.getenv("COHERE_API_KEY"):
        return "cohere"
    if os.getenv("AWS_PROFILE") or os.getenv("AWS_ACCESS_KEY_ID"):
        return "bedrock"
    if os.getenv("HUGGINGFACEHUB_API_TOKEN"):
        return "huggingface"
    if os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_ENABLED"):
        return "ollama"
    # Final fallback
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "openai"


def get_default_model() -> str:
    """Get the default model name based on available provider.

    Returns:
        Default model name for the detected provider. Can be overridden
        with environment variables like ANTHROPIC_MODEL_NAME, OPENAI_MODEL_NAME, etc.
    """
    provider = detect_provider()

    # Allow override via environment variables
    env_model_names = {
        "anthropic": os.getenv("ANTHROPIC_MODEL_NAME"),
        "openai": os.getenv("OPENAI_MODEL_NAME"),
        "ollama": os.getenv("OLLAMA_MODEL_NAME"),
        "azure_openai": os.getenv("AZURE_OPENAI_MODEL_NAME"),
        "google_vertexai": os.getenv("GOOGLE_VERTEX_MODEL_NAME"),
        "google_genai": os.getenv("GOOGLE_GENAI_MODEL_NAME"),
        "mistralai": os.getenv("MISTRAL_MODEL_NAME"),
        "cohere": os.getenv("COHERE_MODEL_NAME"),
        "bedrock": os.getenv("BEDROCK_MODEL_NAME"),
        "huggingface": os.getenv("HUGGINGFACE_MODEL_NAME"),
    }

    if env_model_name := env_model_names.get(provider):
        return env_model_name

    return DEFAULT_MODELS.get(provider, "gpt-4o-mini")


# Registry of LLM provider factories
_FACTORIES: dict[Provider, Callable[[str, float], Any]] = {}

# Model instance cache to avoid repeated initialization.
# Key: (model_name, temperature, provider_key)
_MODEL_CACHE: dict[tuple[str, float, str], Any] = {}
_MODEL_CACHE_LOCK = threading.Lock()

# Default request timeout for LLM API calls (seconds).
_DEFAULT_REQUEST_TIMEOUT = 60


def _get_request_timeout() -> int:
    """Get the request timeout from env var with safe fallback.

    Returns:
        Timeout in seconds, defaults to _DEFAULT_REQUEST_TIMEOUT.
    """
    try:
        return int(os.getenv("OPENAI_REQUEST_TIMEOUT", str(_DEFAULT_REQUEST_TIMEOUT)))
    except (ValueError, TypeError):
        return _DEFAULT_REQUEST_TIMEOUT


def register_provider(provider: Provider) -> Callable:
    """Decorator to register an LLM factory."""

    def decorator(factory: Callable[[str, float], Any]) -> Callable:
        _FACTORIES[provider] = factory
        return factory

    return decorator


@register_provider("anthropic")
def _create_anthropic(model_name: str, temperature: float) -> Any:
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model_name, temperature=temperature)  # type: ignore[call-arg]


@register_provider("ollama")
def _create_ollama(model_name: str, temperature: float) -> Any:
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=model_name,
        temperature=temperature,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )


@register_provider("azure_openai")
def _create_azure_openai(model_name: str, temperature: float) -> Any:
    from langchain_openai import AzureChatOpenAI

    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    return AzureChatOpenAI(
        model=model_name,
        temperature=temperature,
        api_key=SecretStr(api_key) if api_key else None,
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    )


@register_provider("google_vertexai")
def _create_google_vertexai(model_name: str, temperature: float) -> Any:
    from langchain_google_vertexai import ChatVertexAI

    return ChatVertexAI(model=model_name, temperature=temperature)


@register_provider("google_genai")
def _create_google_genai(model_name: str, temperature: float) -> Any:
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=model_name, temperature=temperature)


@register_provider("mistralai")
def _create_mistralai(model_name: str, temperature: float) -> Any:
    from langchain_mistralai import ChatMistralAI

    return ChatMistralAI(model_name=model_name, temperature=temperature)


@register_provider("cohere")
def _create_cohere(model_name: str, temperature: float) -> Any:
    from langchain_cohere import ChatCohere

    return ChatCohere(model=model_name, temperature=temperature)


@register_provider("bedrock")
def _create_bedrock(model_name: str, temperature: float) -> Any:
    from langchain_aws import ChatBedrock

    if bedrock_region := os.getenv("BEDROCK_REGION"):
        os.environ["AWS_DEFAULT_REGION"] = bedrock_region
    return ChatBedrock(model=model_name, temperature=temperature)


@register_provider("huggingface")
def _create_huggingface(model_name: str, temperature: float) -> Any:
    from langchain_huggingface import ChatHuggingFace

    try:
        return ChatHuggingFace(model_id=model_name, temperature=temperature)
    except Exception:
        return ChatHuggingFace(model_id=model_name)


@register_provider("openai")
def _create_openai(model_name: str, temperature: float) -> Any:
    from langchain_openai.chat_models.base import ChatOpenAI

    openai_api_key = os.getenv("OPENAI_API_KEY")
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=SecretStr(openai_api_key) if openai_api_key else None,
        max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "3")),
        timeout=_get_request_timeout(),
    )


def _looks_like_ollama_model(model_name: str) -> bool:
    """Check if a model name looks like an Ollama/local model.

    Args:
        model_name: The model name to check.

    Returns:
        True if the model name appears to be a local/Ollama model.

    Note:
        This specifically excludes models that might be z.ai models (e.g., glm-4.5-air).
        Ollama models typically have patterns like: llama3.2, glm-4-flash, mistral:latest
    """
    # Models that are definitely Ollama/local (not cloud providers)
    # Exclude "glm-" prefix since z.ai uses that pattern (glm-4.5-air)
    ollama_prefixes = ("llama", "mistral", "codellama", "phi", "gemma", "qwen", "deepseek")
    # Also check for common Ollama model suffixes
    ollama_suffixes = ("-flash", "-coder", "-instruct", ":latest", ":v")
    name_lower = model_name.lower()
    has_prefix = any(name_lower.startswith(prefix) for prefix in ollama_prefixes)
    has_suffix = any(suffix in name_lower for suffix in ollama_suffixes)
    return has_prefix or has_suffix


def _is_glm_model(model_name: str) -> bool:
    """Check if a model name is a GLM model (z.ai).

    Args:
        model_name: The model name to check.

    Returns:
        True if the model name appears to be a GLM/z.ai model.
    """
    name_lower = model_name.lower()
    # GLM models from z.ai typically start with "glm-" or "glm" followed by version
    # Examples: glm-4.7, glm-4-flash, glm-4.5-air
    return name_lower.startswith("glm")


def _cache_and_return(cache_key: tuple[str, float, str], model: Any) -> Any:
    """Store a model instance in the cache and return it."""
    with _MODEL_CACHE_LOCK:
        _MODEL_CACHE[cache_key] = model
    return model


def _create_model(model_name: str, temperature: float) -> Any:
    """Create the appropriate LLM model instance based on the detected provider.

    Uses a cache keyed by (model_name, temperature, provider) to avoid
    re-initializing the same model on every call.

    Args:
        model_name: Name of the model to use.
        temperature: Temperature setting for the model.

    Returns:
        The appropriate Chat model instance for the detected provider.
    """
    provider = detect_provider()

    # Check cache first (thread-safe read)
    cache_key = (model_name, temperature, provider)
    with _MODEL_CACHE_LOCK:
        if cache_key in _MODEL_CACHE:
            return _MODEL_CACHE[cache_key]

    # Debug logging to trace model creation
    logger.debug(
        f"Creating model: name='{model_name}', provider='{provider}', "
        f"OPENAI_BASE_URL='{os.getenv('OPENAI_BASE_URL')}', "
        f"OLLAMA_BASE_URL='{os.getenv('OLLAMA_BASE_URL')}'"
    )

    # Smart routing: if model looks like Ollama AND OLLAMA_BASE_URL is set, use Ollama
    ollama_base_url = os.getenv("OLLAMA_BASE_URL")
    openai_base_url = os.getenv("OPENAI_BASE_URL")

    # If using OpenAI provider with a non-OpenAI base URL (like z.ai), don't redirect to Ollama
    is_custom_openai_endpoint = openai_base_url and "openai.com" not in openai_base_url

    looks_like_ollama = _looks_like_ollama_model(model_name)
    if provider == "openai" and ollama_base_url and looks_like_ollama and not is_custom_openai_endpoint:
        logger.info(f"Model '{model_name}' looks like an Ollama model - routing to Ollama at {ollama_base_url}")
        return _cache_and_return(cache_key, _create_ollama(model_name, temperature))

    # Check for z.ai GLM models: if model starts with "glm" and OPENAI_BASE_URL is set
    # to a non-OpenAI endpoint (like z.ai), route to the custom endpoint
    if provider == "openai" and _is_glm_model(model_name) and is_custom_openai_endpoint:
        logger.info(
            f"Model '{model_name}' is a GLM model on OpenAI provider - "
            f"routing to OpenAI-compatible API at {openai_base_url}"
        )
        return _cache_and_return(cache_key, _create_openai(model_name, temperature))

    # Default to the provider's factory
    factory = _FACTORIES.get(provider)
    if factory:
        return _cache_and_return(cache_key, factory(model_name, temperature))

    # Fallback to OpenAI
    return _cache_and_return(cache_key, _create_openai(model_name, temperature))
