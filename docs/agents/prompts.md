# Prompt Management

Manage agent prompts through files, configuration, or code.

## Prompt Loading Order

whaagent loads prompts in this order (first match wins):

1. **Config inline**: `agents.prompts.<name>` in `.whaagent.yaml`
2. **Config directory**: `<prompts_dir>/<name>.md` file
3. **Bundled**: `whaagent/prompts/<name>.md` in package
4. **Hardcoded**: Fallback in agent class

## Configuration-Based Prompts

### Inline in Config

```yaml
# .whaagent.yaml
agents:
  prompts:
    developer: |
      You are a Principal Software Engineer.
      Your goal is to help users understand and maintain codebases.

      ## Capabilities
      - Search code with ripgrep
      - Explore project structure
      - Read and edit files

    learning: |
      You are an educational assistant.
      Create step-by-step tutorials for any topic.
```

### From Directory

```yaml
# .whaagent.yaml
agents:
  prompts_dir: ./prompts  # Directory containing .md files
```

Create prompt files:
```
prompts/
├── developer.md
├── learning.md
└── custom.md
```

## File-Based Prompts

Create markdown files for complex prompts:

```markdown
<!-- prompts/custom.md -->
# Custom Agent Prompt

You are a specialized assistant for [domain].

## Primary Responsibilities
1. [responsibility 1]
2. [responsibility 2]

## Capabilities
- [capability 1]
- [capability 2]

## Guidelines
- Always [guideline 1]
- Never [guideline 2]

## Output Format
When responding:
1. Start with a summary
2. Provide details
3. End with next steps
```

## Programmatic Usage

### Load Prompt

```python
from whaagent import load_prompt

# Load with automatic fallback
prompt = load_prompt("developer")
if prompt:
    print(prompt)
else:
    print("No prompt found")
```

### Agent with External Prompt

```python
from whaagent import AgentBase, AgentRegistry, load_prompt

@AgentRegistry.register("custom")
class CustomAgent(AgentBase):
    @property
    def system_prompt(self) -> str:
        prompt = load_prompt("custom")
        if prompt:
            return prompt
        # Fallback
        return "You are a helpful assistant."
```

### Dynamic Prompt from File

```python
from pathlib import Path
from whaagent import AgentBase

class DynamicPromptAgent(AgentBase):
    def __init__(self, prompt_path: str, **kwargs):
        self._prompt_path = prompt_path
        super().__init__(**kwargs)

    @property
    def system_prompt(self) -> str:
        return Path(self._prompt_path).read_text()
```

## Bundled Prompts

whaagent includes default prompts for bundled agents:

| Agent | File |
|-------|------|
| developer | `whaagent/prompts/developer.md` |
| github-pr-reviewer | `whaagent/prompts/github_pr_reviewer.md` |
| learning | `whaagent/prompts/learning.md` |
| news | `whaagent/prompts/news.md` |
| youtube | `whaagent/prompts/youtube.md` |

Override these by creating files in your `prompts_dir`.

## Prompt Best Practices

### Structure

```markdown
# Role Description
[One sentence describing the agent's role]

## Capabilities
- [What the agent can do]

## Guidelines
- [How the agent should behave]

## Output Format
[How responses should be structured]
```

### Be Specific

```markdown
# Good
You are a Python code reviewer. Focus on:
- PEP 8 compliance
- Type hints
- Docstrings
- Error handling

# Bad
You are a code reviewer.
```

### Include Examples

```markdown
## Example Interaction

User: "Explain this function"
Agent: "This function calculates the factorial of a number..."
```

### Set Boundaries

```markdown
## Limitations
- Cannot execute code
- Cannot modify files outside the project
- Cannot access external APIs without MCP
```

## Environment-Specific Prompts

Use different prompts for different environments:

```yaml
# .whaagent.yaml (development)
agents:
  prompts:
    developer: |
      You are in DEVELOPMENT mode.
      Be verbose and explain your reasoning.

# .whaagent.prod.yaml (production)
agents:
  prompts:
    developer: |
      You are in PRODUCTION mode.
      Be concise and action-oriented.
```

```bash
# Development
export whaagent_CONFIG=.whaagent.yaml

# Production
export whaagent_CONFIG=.whaagent.prod.yaml
```

## See Also

- [Configuration](../configuration.md) - Full configuration options
- [Custom Agents](custom.md) - Create agents
- [Built-in Agents](built-in.md) - Bundled agents
