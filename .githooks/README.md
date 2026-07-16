# Git hooks

These hooks run the same steps as CI so you can catch failures before pushing.

## Setup (one-time)

Tell Git to use this directory for hooks:

```bash
git config core.hooksPath .githooks
```

Make the hook executable (if needed):

```bash
chmod +x .githooks/pre-push
```

## Hooks

- **pre-push** — Runs `uv sync`, `make check`, and `make test` before every `git push`. Push is aborted if any step fails.

## Skip hooks once

To push without running the hook (use sparingly):

```bash
git push --no-verify
```
