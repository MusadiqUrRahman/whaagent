---
name: whaagent-add-agent
description: Scaffold a new whaagent agent with agent.py, prompt.md, and test file
disable-model-invocation: true
---

# Add Agent Skill

Scaffold a new whaagent agent with all required files.

## Steps

1. Ask the user for:
   - **Agent name** (kebab-case, e.g. `my-agent`)
   - **Description** (one-line summary)
   - **MCP servers** (optional, e.g. `["toolbox"]`)
   - **Tool categories** (optional, e.g. `["web", "code"]`)

2. Create `src/whaagent/agents/{name}.py` using this template:

```python
from typing import Any, Sequence

from whaagent.agent import AgentBase
from whaagent.prompts import load_prompt
from whaagent.registry import AgentRegistry


@AgentRegistry.register("{name}", mcp_servers=[{mcp_servers}], tool_categories=[{tool_categories}])
class {ClassName}Agent(AgentBase):
    """Agent description here."""

    @property
    def system_prompt(self) -> str:
        return load_prompt("{name}")

    def local_tools(self) -> Sequence[Any]:
        return []
```

Where `{ClassName}` is the name converted to PascalCase (e.g. `my-agent` -> `MyAgent`).

3. Create `src/whaagent/prompts/{name}.md` with a minimal system prompt:

```markdown
You are a {description}.

Your role is to assist users with {description}.
```

4. Create `tests/test_{name}_agent.py` with basic tests:

```python
"""Tests for the {name} agent."""
from whaagent.agents.{name} import {ClassName}Agent


def test_agent_class_exists():
    """Test that the agent class can be imported."""
    assert {ClassName}Agent is not None


def test_agent_has_correct_name():
    """Test that the agent is registered with the correct name."""
    # The agent is registered via @AgentRegistry.register decorator
    agent_cls = {ClassName}Agent
    assert agent_cls is not None
```

5. Export the agent from `src/whaagent/agents/__init__.py` if needed.

6. Run `make check && make test` to verify everything works.

## Reference

Existing agents follow this pattern:
- `assistant.py` — generalist with MCP toolbox
- `developer.py` — code exploration with local tools
- `committer.py` — git commit automation
- `learning.py` — educational content
- `news.py` — news aggregation
- `ollama.py` — Ollama-backed
- `youtube.py` — YouTube transcript extraction
- `github_pr_reviewer.py` — PR review automation
