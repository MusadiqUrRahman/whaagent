# Configuration

whaagent uses YAML configuration files with environment variable support for flexible setup.

## Configuration File

### Location Search Order

whaagent searches for configuration in this order:

1. `./.whaagent.yaml` (current directory)
2. `~/.whaagent.yaml` (home directory)
3. `whaagent_CONFIG` environment variable path

### Example Configuration

```yaml
# .whaagent.yaml

# LLM Configuration
llm:
  provider: anthropic              # Optional: auto-detect if not set
  model: claude-sonnet-4-6         # Optional: use provider default
  temperature: 0.7
  max_tokens: 4096                 # Optional

# Logging Configuration
logging:
  level: INFO                      # DEBUG, INFO, WARNING, ERROR
  directory: ./logs                # Optional: log directory
  file: agent.log                  # Optional: log file name

# MCP Configuration
mcp:
  connection_timeout: 15           # Seconds to wait for MCP connections
  fail_fast: true                  # Fail on first connection error

  # Bundled servers (can be overridden)
  servers:
    fetch:
      url: https://remote.mcpservers.org/fetch/mcp
      transport: http
    web-forager:
      command: uvx
      args: ["web-forager"]
      transport: stdio

  # Custom servers
  custom:
    my-custom-server:
      url: https://my-server.com/mcp
      transport: sse

# Agent Configuration
agents:
  prompts_dir: ./prompts           # Directory for .md prompt files

  # Prompt overrides (optional, replaces prompts_dir lookup)
  prompts:
    developer: |
      You are a Principal Software Engineer...

  # Default agent settings
  defaults:
    timeout: 300
    thread_id: "default"
```

## Environment Variables

### LLM Provider Keys

```bash
# Anthropic (Claude)
ANTHROPIC_API_KEY=sk-ant-xxx

# OpenAI (GPT)
OPENAI_API_KEY=sk-xxx

# Google (Gemini)
GOOGLE_API_KEY=xxx

# Mistral
MISTRAL_API_KEY=xxx

# Cohere
COHERE_API_KEY=xxx

# AWS Bedrock
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_REGION=us-east-1

# Groq
GROQ_API_KEY=xxx

# HuggingFace
HUGGINGFACEHUB_API_TOKEN=xxx

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
```

### Framework Variables

```bash
# Custom config file path
whaagent_CONFIG=/path/to/config.yaml

# Custom agents package
whaagent_AGENTS_PACKAGE=my_package.agents
```

## Programmatic Configuration

```python
from whaagent import whaagentConfig, set_config, get_config

# Load from file
config = whaagentConfig.load("/path/to/config.yaml")

# Or create programmatically
from whaagent.config import LLMConfig, LoggingConfig

config = whaagentConfig(
    llm=LLMConfig(
        provider="anthropic",
        model="claude-sonnet-4-6",
        temperature=0.7,
    ),
    logging=LoggingConfig(
        level="DEBUG",
    ),
)

# Set as global config
set_config(config)

# Later, retrieve config
config = get_config()
```

## Configuration Sections

### LLM Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `provider` | str | auto | LLM provider name |
| `model` | str | provider default | Model identifier |
| `temperature` | float | 0.7 | Sampling temperature |
| `max_tokens` | int | None | Maximum output tokens |

### Logging Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `level` | str | INFO | Log level (DEBUG, INFO, WARNING, ERROR) |
| `directory` | Path | ~/.whaagent/logs | Log directory |
| `file` | str | None | Log file name |

### MCP Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `connection_timeout` | int | 15 | Connection timeout in seconds |
| `fail_fast` | bool | True | Fail on first connection error |
| `servers` | dict | bundled | MCP server configurations |
| `custom` | dict | {} | Custom server configurations |

### Agents Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `prompts_dir` | Path | None | Directory for prompt files |
| `prompts` | dict | {} | Inline prompt overrides |
| `defaults` | dict | {} | Default agent settings |

## See Also

- [LLM Providers](llm/providers.md) - Provider-specific setup
- [MCP Servers](mcp/servers.md) - MCP server configuration
- [Agent Prompts](agents/prompts.md) - Prompt management
