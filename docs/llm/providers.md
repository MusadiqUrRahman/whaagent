# LLM Provider Setup

Detailed setup instructions for each LLM provider.

## Anthropic (Claude)

**Recommended provider for whaagent.**

### Setup

1. Get API key from [Anthropic Console](https://console.anthropic.com/)
2. Set environment variable:
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-xxx
   ```

### Models

| Model | Description |
|-------|-------------|
| `claude-opus-4-6` | Most capable |
| `claude-sonnet-4-6` | Balanced (default) |
| `claude-haiku-4-5` | Fast and efficient |

### Usage

```python
from whaagent import AgentBase, AgentRegistry

@AgentRegistry.register("claude-agent")
class ClaudeAgent(AgentBase):
    def __init__(self, **kwargs):
        super().__init__(model_name="claude-sonnet-4-6", **kwargs)
```

---

## OpenAI (GPT)

### Setup

1. Get API key from [OpenAI Platform](https://platform.openai.com/)
2. Set environment variable:
   ```bash
   export OPENAI_API_KEY=sk-xxx
   ```

### Models

| Model | Description |
|-------|-------------|
| `gpt-4o` | Latest flagship (default) |
| `gpt-4o-mini` | Fast and cost-effective |
| `o1-preview` | Advanced reasoning |

### Usage

```python
@AgentRegistry.register("gpt-agent")
class GPTAgent(AgentBase):
    def __init__(self, **kwargs):
        super().__init__(model_name="gpt-4o", **kwargs)
```

---

## Google Gemini

### Setup

1. Get API key from [Google AI Studio](https://aistudio.google.com/)
2. Set environment variable:
   ```bash
   export GOOGLE_API_KEY=xxx
   ```

### Models

| Model | Description |
|-------|-------------|
| `gemini-1.5-pro` | Most capable (default) |
| `gemini-1.5-flash` | Fast |
| `gemini-1.0-pro` | Standard |

### Usage

```python
@AgentRegistry.register("gemini-agent")
class GeminiAgent(AgentBase):
    def __init__(self, **kwargs):
        super().__init__(model_name="gemini-1.5-pro", **kwargs)
```

---

## Google Vertex AI

For enterprise Google Cloud users.

### Setup

1. Set up [Google Cloud service account](https://cloud.google.com/vertex-ai)
2. Set environment variable:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
   export VERTEXAI_PROJECT=my-project
   export VERTEXAI_LOCATION=us-central1
   ```

### Usage

```yaml
llm:
  provider: google-vertexai
  model: gemini-1.5-pro
```

---

## Mistral

### Setup

1. Get API key from [Mistral Platform](https://console.mistral.ai/)
2. Set environment variable:
   ```bash
   export MISTRAL_API_KEY=xxx
   ```

### Models

| Model | Description |
|-------|-------------|
| `mistral-large-latest` | Most capable (default) |
| `mistral-medium-latest` | Balanced |
| `codestral-latest` | Code-focused |

---

## Cohere

### Setup

1. Get API key from [Cohere Dashboard](https://dashboard.cohere.com/)
2. Set environment variable:
   ```bash
   export COHERE_API_KEY=xxx
   ```

### Models

| Model | Description |
|-------|-------------|
| `command-r-plus` | Most capable (default) |
| `command-r` | Efficient |

---

## AWS Bedrock

### Setup

1. Configure AWS credentials:
   ```bash
   export AWS_ACCESS_KEY_ID=xxx
   export AWS_SECRET_ACCESS_KEY=xxx
   export AWS_REGION=us-east-1
   ```

### Models

Bedrock provides access to multiple foundation models:
- `anthropic.claude-3-sonnet`
- `anthropic.claude-3-opus`
- `meta.llama3-70b-instruct`
- And more

---

## Groq

Fast inference with Llama and Mixtral models.

### Setup

1. Get API key from [Groq Console](https://console.groq.com/)
2. Set environment variable:
   ```bash
   export GROQ_API_KEY=xxx
   ```

### Models

| Model | Description |
|-------|-------------|
| `llama-3.1-70b-versatile` | Default |
| `llama-3.1-8b-instant` | Fast |
| `mixtral-8x7b-32768` | Mixtral |

---

## HuggingFace

### Setup

1. Get token from [HuggingFace Settings](https://huggingface.co/settings/tokens)
2. Set environment variable:
   ```bash
   export HUGGINGFACEHUB_API_TOKEN=xxx
   ```

### Models

Any model from HuggingFace Hub. Example:
- `meta-llama/Llama-3.2-3B-Instruct`

---

## Ollama (Local)

Run models locally with Ollama.

### Setup

1. Install [Ollama](https://ollama.ai/)
2. Pull a model: `ollama pull llama3.2`
3. Set environment variable (optional):
   ```bash
   export OLLAMA_BASE_URL=http://localhost:11434
   ```

### Models

Any model pulled with Ollama:
- `llama3.2` (default)
- `mistral`
- `codellama`

### Usage

```yaml
llm:
  provider: ollama
  model: llama3.2
```

---

## See Also

- [LLM Overview](index.md) - Provider overview
- [Configuration](../configuration.md) - Configuration options
