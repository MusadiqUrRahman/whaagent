# LLM Providers

This document provides detailed information about all LLM providers supported by the Agentic Framework.

## Provider Overview

| Provider | Type | Use Case | API Key Required? |
|----------|------|----------|-------------------|
| **Anthropic** | Cloud | State-of-the-art reasoning (Claude) | Yes* |
| **OpenAI** | Cloud | GPT-4, GPT-4.1, o1 series | Yes* |
| **Azure OpenAI** | Cloud | Enterprise OpenAI deployments | No |
| **Google GenAI** | Cloud | Gemini models via API | No |
| **Google Vertex AI** | Cloud | Gemini models via GCP | No |
| **Groq** | Cloud | Ultra-fast inference | No |
| **Mistral AI** | Cloud | European privacy-focused models | No |
| **Cohere** | Cloud | Enterprise RAG and Command models | No |
| **AWS Bedrock** | Cloud | Anthropic, Titan, Meta via AWS | No |
| **Ollama** | Local | Run LLMs locally (zero API cost) | No |
| **Hugging Face** | Cloud | Open models from Hugging Face Hub | No |

**Provider Priority:** Anthropic > Google Vertex > Google GenAI > Azure > Groq > Mistral > Cohere > Bedrock > HuggingFace > Ollama > OpenAI (fallback)

---

## Environment Variables

### Anthropic

```bash
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL_NAME=claude-haiku-4-5-20251001  # Optional
```

**Default Model:** `claude-haiku-4-5-20251001`

---

### OpenAI

```bash
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL_NAME=gpt-4o-mini  # Optional
```

**Default Model:** `gpt-4o-mini`

---

### Azure OpenAI

```bash
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_MODEL_NAME=gpt-4o-mini  # Optional
AZURE_OPENAI_API_VERSION=2024-02-15-preview  # Optional
```

**Default Model:** `gpt-4o-mini`

---

### Google GenAI

```bash
GOOGLE_API_KEY=your-google-key
GOOGLE_GENAI_MODEL_NAME=gemini-2.0-flash-exp  # Optional
```

**Default Model:** `gemini-2.0-flash-exp`

---

### Google Vertex AI

```bash
GOOGLE_VERTEX_PROJECT_ID=your-project-id
GOOGLE_VERTEX_LOCATION=us-central1  # Optional
GOOGLE_VERTEX_MODEL_NAME=gemini-2.0-flash-exp  # Optional
```

**Default Model:** `gemini-2.0-flash-exp`

---

### Groq

```bash
GROQ_API_KEY=gsk-your-key-here
GROQ_MODEL_NAME=llama-3.3-70b-versatile  # Optional
```

**Default Model:** `llama-3.3-70b-versatile`

---

### Mistral AI

```bash
MISTRAL_API_KEY=your-mistral-key-here
MISTRAL_MODEL_NAME=mistral-large-latest  # Optional
```

**Default Model:** `mistral-large-latest`

---

### Cohere

```bash
COHERE_API_KEY=your-cohere-key-here
COHERE_MODEL_NAME=command-r-plus  # Optional
```

**Default Model:** `command-r-plus`

---

### AWS Bedrock

```bash
AWS_PROFILE=your-profile
# OR
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1  # Optional
BEDROCK_MODEL_NAME=anthropic.claude-3-5-sonnet-20241022-v2:0  # Optional
```

**Default Model:** `anthropic.claude-3-5-sonnet-20241022-v2:0`

---

### Ollama

```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_NAME=llama3.2  # Optional
```

**Default Model:** `llama3.2`

**Requirements:** Ollama must be running locally with the specified model available.

---

### Hugging Face

```bash
HUGGINGFACEHUB_API_TOKEN=your-hf-token
HUGGINGFACEHUB_MODEL_NAME=meta-llama/Llama-3.2-3B-Instruct  # Optional
```

**Default Model:** `meta-llama/Llama-3.2-3B-Instruct`

---

## Provider Comparison

### Anthropic (Claude)
- **Pros:** Best reasoning capabilities, excellent code understanding, strong safety guardrails
- **Cons:** Higher cost per token
- **Best for:** Complex reasoning, code analysis, multi-step tasks

### OpenAI (GPT)
- **Pros:** Widely available, good general capabilities
- **Cons:** Can be more expensive than alternatives
- **Best for:** General-purpose tasks, when Anthropic key not available

### Google GenAI / Vertex AI (Gemini)
- **Pros:** Fast, good multimodal capabilities, competitive pricing
- **Cons:** API changes more frequently
- **Best for:** Cost-sensitive workloads, Google Cloud users

### Groq
- **Pros:** Extremely fast inference (low latency)
- **Cons:** Uses open-source models (may have different quality profiles)
- **Best for:** Real-time applications, speed-critical tasks

### Ollama
- **Pros:** Free (after initial compute), privacy, no API limits
- **Cons:** Requires local compute resources, quality depends on model
- **Best for:** Development, privacy-sensitive work, offline use

---

## Setup Instructions

### 1. Copy the Environment Template

```bash
cp .env.example .env
```

### 2. Configure Your Provider

Edit `.env` and add credentials for your preferred provider. You only need one provider configured:

```bash
# Choose ONE of the following:

# Anthropic (Recommended)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# OR OpenAI
OPENAI_API_KEY=sk-your-key-here

# OR Google
GOOGLE_API_KEY=your-google-key

# OR Groq
GROQ_API_KEY=gsk-your-key-here

# OR Ollama (Local, no API key needed)
OLLAMA_BASE_URL=http://localhost:11434
```

### 3. Verify Configuration

```bash
# List available agents to verify the framework is working
bin/agent.sh list

# Run a simple agent
bin/agent.sh simple -i "Hello, can you hear me?"
```

---

## Model Selection

The framework uses provider priority to automatically select the best available provider. You can override this with model-specific environment variables:

```bash
# Force a specific model
ANTHROPIC_MODEL_NAME=claude-sonnet-4-6
OPENAI_MODEL_NAME=gpt-4o
GROQ_MODEL_NAME=llama-3.3-70b-versatile
```

Or use the model selection in the agent configuration:

```python
# In your agent configuration or .env file
MODEL_NAME="claude-sonnet-4-6"  # Will use the provider's model
```

---

## Switching Providers

To switch between providers without changing code:

1. Update your `.env` file with the new provider's credentials
2. Remove or comment out the old provider's credentials
3. Run your agent - it will auto-detect the active provider

The framework automatically detects which provider to use based on available environment variables.

---

## Troubleshooting

### No provider detected
Ensure at least one provider's API key is set in your `.env` file.

### Ollama connection refused
Make sure Ollama is running: `ollama serve`

### Rate limits
Consider using a different provider or Ollama for local inference.

### Model not found
Check the model name is correct for your provider and that the model is available in your region/subscription.
