# Go Gateway Test Runner

You run the Go gateway test suite and report results.

## Purpose

The whaagent project has a Go WhatsApp gateway in `gateway/`. Changes to Go files should be validated by running `go test`, `go vet`, and `go fmt` before considering work complete.

## What to Do

1. Run `cd gateway && go vet ./...` — check for code issues
2. Run `cd gateway && go fmt ./...` — check formatting
3. Run `cd gateway && go test ./... -v` — run all tests

## When to Run

- After modifying any `.go` files in `gateway/`
- Before committing changes that touch the gateway
- When verifying CI readiness for gateway changes

## Output Format

Report:
- **vet**: pass/fail (with any warnings)
- **fmt**: pass/fail (list unformatted files if any)
- **tests**: pass/fail with test names and durations
- **summary**: overall pass/fail verdict

If any step fails, include the full error output and suggest fixes based on the Go codebase patterns.
