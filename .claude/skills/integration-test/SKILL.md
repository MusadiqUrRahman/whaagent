---
name: integration-test
description: Run end-to-end integration verification after code changes. Unit tests mock prompt loading, tool registration, and agent instantiation — they pass even when wiring is broken. This skill catches those gaps.
---

# Integration Test Skill

After `make check && make test` passes, run an end-to-end smoke test to verify the full wiring (prompt loading, tool registration, agent instantiation) works — not just unit tests.

## When to Use

After ANY code change, before telling the user it's ready to push/deploy. This applies to all changes — tools, agents, prompts, config, dependencies, imports — not just tool/agent code.

## Why

Unit tests mock prompt loading, tool registration, and agent instantiation. They pass even when wiring is broken (wrong filename, missing prompt, import error, missing dependency). The only way to catch these is exercising the real application.

## Steps

### 1. Verify all agents can load their prompts

```bash
whaagent list
```

Every agent listed should be instantiable. If this fails, the wiring is broken — fix before proceeding.

### 2. Test the changed component through the full pipeline

```bash
whaagent chat "test message relevant to the change" -a <agent-name>
```

- If you changed a tool used by the assistant, test with the assistant: `whaagent chat "test" -a assistant`
- If you changed a specific agent, test that agent: `whaagent chat "test" -a <agent-name>`
- If you changed shared infrastructure (graph, config, prompts), test with the default assistant

This exercises real prompt loading, tool registration, LLM routing — the full wiring.

### 3. Verify no import or startup errors

Check the command output for warnings like:
- `Failed to generate system prompt`
- `Prompt '...' not found`
- `ImportError`
- `ModuleNotFoundError`

These are wiring errors that unit tests won't catch.

### 4. Only then tell the user it's ready to push/deploy.

## Checklist

- [ ] `make check && make test` passes
- [ ] `whaagent list` succeeds — all agents loadable
- [ ] `whaagent chat "test" -a <relevant-agent>` succeeds — no wiring errors
- [ ] No warnings or errors in output
