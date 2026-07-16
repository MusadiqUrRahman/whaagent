# CLI Reference

whaagent provides a command-line interface for running and managing agents.

## Installation

The CLI is included with the base package:

```bash
pip install whaagent
```

## Global Options

```bash
whaagent [OPTIONS] COMMAND
```

| Option | Description |
|--------|-------------|
| `--verbose`, `-v` | Enable verbose/debug logging |
| `--help` | Show help message |

## Commands

### list

List all available agents.

```bash
whaagent list
```

Example output:
```
Available Agents: developer, github-pr-reviewer, learning, news, youtube
```

### info

Show detailed information about an agent.

```bash
whaagent info <agent-name>
```

Example:
```bash
whaagent info developer
```

Output includes:
- Agent class name
- Module location
- MCP servers configured
- System prompt
- Available tools

### config

Show current configuration.

```bash
whaagent config
```

Displays:
- LLM settings
- Logging configuration
- MCP server list
- Agent defaults

### Running Agents

Each registered agent gets its own command:

```bash
whaagent <agent-name> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--input`, `-i` | Input text for the agent (required) |
| `--timeout`, `-t` | Max runtime in seconds (default: 600) |

#### Examples

```bash
# Run developer agent
whaagent developer -i "Explain the project structure"

# With custom timeout
whaagent developer -i "Analyze all Python files" -t 1200

# Learning agent
whaagent learning -i "Teach me about async/await in Python"

# News agent
whaagent news -i "What's happening in AI today?"

# YouTube agent
whaagent youtube -i "Summarize video dQw4w9WgXcQ"
```

## Docker Usage

For Docker deployments, use the wrapper script:

```bash
# List agents
bin/whaagent.sh list

# Run an agent
bin/whaagent.sh developer -i "Explain this code"

# With verbose output
bin/whaagent.sh -v developer -i "Debug the authentication flow"
```

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (agent not found, timeout, MCP error, etc.) |

## Error Handling

### Agent Not Found

```bash
whaagent info nonexistent
# Error: Agent 'nonexistent' not found.
# Tip: Use 'list' command to see all available agents.
```

### Timeout

```bash
whaagent developer -i "Complex task" -t 10
# Error running agent: Run timed out after 10s.
# Check MCP server connectivity or use --timeout to increase.
```

### MCP Connection Error

```bash
whaagent developer -i "Fetch data"
# MCP Connectivity Error: Failed to connect to fetch server
# Suggestion: Ensure that MCP server URL is correct and you have network access.
```

## Programmatic Usage

```python
from whaagent.cli import execute_agent

# Execute an agent programmatically
result = execute_agent(
    agent_name="developer",
    input_text="Explain this codebase",
    timeout_sec=300,
)
print(result)
```

## See Also

- [Getting Started](getting-started.md) - Installation and first steps
- [Built-in Agents](agents/built-in.md) - Available agents
- [Configuration](configuration.md) - Configuration options
