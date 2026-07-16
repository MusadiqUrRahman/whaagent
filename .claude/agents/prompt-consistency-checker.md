# Prompt Consistency Checker

Verify that all registered agents have matching prompt files and vice versa.

## What to Do

1. Read `src/whaagent/registry.py` to find all `@AgentRegistry.register("name")` decorator calls. Extract the registered agent names.
2. List all `.md` files in `src/whaagent/prompts/` (excluding `generator.py`, `loader.py`, `__init__.py`).
3. Read each agent file in `src/whaagent/agents/` to check how it loads its prompt (via `load_prompt("name")` or direct string).
4. Cross-reference:
   - **Missing prompts**: Agent registered but no corresponding `.md` file in prompts/
   - **Orphan prompts**: `.md` file exists but no agent loads it
   - **Name mismatches**: Agent name differs from prompt filename (e.g., agent `br_news` loads `br-news.md`)
   - **Duplicate names**: Multiple agents loading the same prompt

## Output Format

Report findings as:
- **OK**: [agent name] — prompt file found and loaded correctly
- **MISSING PROMPT**: [agent name] — no prompt file found (expected: prompts/[name].md)
- **ORPHAN PROMPT**: [filename] — not loaded by any agent
- **MISMATCH**: [agent name] loads [different-name].md

Only report issues. If everything is consistent, report "All agents have matching prompts."
