# Python Dependency Auditor

Cross-reference declared dependencies against actual imports to find unused or missing packages.

## What to Do

1. Read `pyproject.toml` and extract all package names from the `dependencies` array.
2. Search `src/whaagent/` for all `import` statements using grep: `import X`, `from X import`.
3. Map package names to import names where they differ (e.g., `langchain-openai` → `langchain_openai`).
4. Cross-reference:
   - **Unused deps**: Packages in pyproject.toml with no corresponding imports in src/
   - **Undeclared imports**: Imports in src/ that don't map to any declared dependency or stdlib module
   - **Dev deps in main**: Packages that should be dev-dependencies but are in main dependencies

## Known Exceptions

Ignore these packages (they're used at runtime but not directly imported):
- `python-dotenv` / `dotenv` — loaded via `os.environ`
- `langgraph-checkpoint-sqlite` — plugin loaded by langgraph
- `langgraph-cli` / `langgraph-api` — CLI/API entry points
- `langchain-model-profiles` — config-driven, no direct import
- `langsmith` — tracing integration loaded by langchain

## Output Format

Report:
- **UNUSED**: [package] — declared but no imports found in src/
- **UNDECLARED**: [import] — imported but not in dependencies
- **OK**: [count] packages verified
- **summary**: X unused, Y undeclared, Z verified
