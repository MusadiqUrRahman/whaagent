# LLM Providers

whaagent supports 10+ LLM providers out of the box.

## Supported Providers

| Provider | Models | Environment Variable |
|----------|--------|---------------------|
| [Anthropic](providers.md#anthropic) | Claude | `ANTHROPIC_API_KEY` |
| [OpenAI](providers.md#openai) | GPT | `OPENAI_API_KEY` |
| [Google Gemini](providers.md#google-gemini) | Gemini | `GOOGLE_API_KEY` |
| [Google Vertex AI](providers.md#google-vertex-ai) | Gemini + others | `GOOGLE_APPLICATION_CREDENTIALS` |
| [Mistral](providers.md#mistral) | Mistral | `MISTRAL_API_KEY` |
| [Cohere](providers.md#cohere) | Command | `COHERE_API_KEY` |
| [AWS Bedrock](providers.md#aws-bedrock) | Multiple | `AWS_ACCESS_KEY_ID` |
| [Groq](providers.md#groq) | Llama, Mixtral | `GROQ_API_KEY` |
| [HuggingFace](providers.md#huggingface) | Open models | `HUGGINGFACEHUB_API_TOKEN` |
| [Ollama](providers.md#ollama) | Local models | `OLLAMA_BASE_URL` |

## Auto-Detection

whaagent automatically detects which provider to use based on environment variables:

```python
from whaagent import detect_provider

provider = detect_provider()
print(f"Using: {provider}")  # e.g., "anthropic"
```

Detection order:
1. Explicit config setting
2. `ANTHROPIC_API_KEY` → Anthropic
3. `OPENAI_API_KEY` → OpenAI
4. `GOOGLE_API_KEY` → Google
5. ... other providers

## Configuration

### Environment Variable

```bash
export ANTHROPIC_API_KEY=sk-ant-xxx
export OPENAI_API_KEY=sk-xxx
```

### YAML Config

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-6
  temperature: 0.7
```

### Programmatic

```python
from whaagent import whaagentConfig, set_config, LLMConfig

config = whaagentConfig(
    llm=LLMConfig(
        provider="anthropic",
        model="claude-sonnet-4-6",
    )
)
set_config(config)
```

## Default Models

Each provider has a default model:

| Provider | Default Model |
|----------|---------------|
| Anthropic | claude-sonnet-4-6 |
| OpenAI | gpt-4o |
| Google Gemini | gemini-1.5-pro |
| Mistral | mistral-large-latest |
| Cohere | command-r-plus |
| AWS Bedrock | anthropic.claude-3-sonnet |
| Groq | llama-3.1-70b-versatile |
| Ollama | llama3.2 |

```python
from whaagent import get_default_model

model = get_default_model("anthropic")
print(model)  # "claude-sonnet-4-6"
```

## Creating Models

```python
from whaagent.llm import create_model

# With provider auto-detection
model = create_model()

# With specific model
model = create_model("claude-sonnet-4-6", temperature=0.7)
```

## Per-Agent Models

Override the model for specific agents:

```python
from whaagent import AgentBase, AgentRegistry

@AgentRegistry.register("creative")
class CreativeAgent(AgentBase):
    def __init__(self, **kwargs):
        super().__init__(
            model_name="claude-sonnet-4-6",
            temperature=0.9,
            **kwargs
        )

    @property
    def system_prompt(self) -> str:
        return "You are a creative writer."
```

## See Also

- [Provider Setup](providers.md) - Detailed setup for each provider
- [Configuration](../configuration.md) - Full configuration options
