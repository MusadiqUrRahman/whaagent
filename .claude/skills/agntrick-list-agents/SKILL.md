---
name: whaagent-list-agents
description: List all registered agents with their configuration — MCP servers, tool categories, prompt status, and local tools. Use when you need to see what agents exist or debug agent registration issues.
---

# whaagent Agent Inventory

Scan all registered agents and report their configuration in a formatted table.

## Steps

1. Grep `src/whaagent/agents/*.py` for `@AgentRegistry.register()` decorators to extract each agent's name, `mcp_servers`, and `tool_categories`.
2. For each agent file, check if it defines `local_tools()` returning any tools.
3. Verify the corresponding prompt `.md` file exists in `src/whaagent/prompts/` by matching the registered name (e.g., agent `br-news` → `br-news.md`, agent `committer` → `committer.md`).
4. Also check for the `assistant` agent which uses a multi-line decorator — grep for it separately.

## Output

Print a markdown table:

| Agent | MCP Servers | Tool Categories | Local Tools | Prompt File |
|-------|-------------|-----------------|-------------|-------------|
| assistant | toolbox | (all) | — | assistant.md |
| developer | toolbox | — | codebase_explorer, code_searcher, syntax_validator, git_command | developer.md |
| ... | ... | ... | ... | ... |

After the table, list any issues:
- **Missing prompt**: Agent registered but no `.md` file found
- **Orphan prompt**: `.md` file exists but no agent loads it
- **No MCP servers**: Agent has no `mcp_servers` configured (may be intentional)
