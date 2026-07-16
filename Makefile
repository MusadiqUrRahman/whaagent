.PHONY: help install run test clean format check docker-build docker-clean build build-clean release gateway-build gateway-test
.DEFAULT_GOAL := help

# Use `uv` for python environment management
UV ?= uv
PYTHON ?= $(UV) run python
PYTEST ?= $(UV) run pytest
RUFF ?= $(UV) run ruff

## -- Help System --

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

## -- Commands --

install: ## Install all dependencies using uv + Playwright browser
	@$(UV) sync
	@$(UV) run playwright install chromium 2>/dev/null || echo "⚠ Playwright browser install skipped (optional for web extraction)"

install-local: ## Install local packages in editable mode (for testing before publishing)
	@$(UV) pip install -e .
	#@$(UV) pip install -e packages/whaagent-whatsapp
	@echo "✓ Local packages installed in editable mode"
	#@git config --local core.hooksPath .githooks

run: ## Run the whaagent CLI to exemplify usage
	@$(UV) run whaagent news -i "What's the latest in AI?"

test: ## Run tests with coverage
	@$(UV) run pytest tests/ -v --cov=src --cov-report=xml --cov-report=term

check: ## Run all checks (mypy, ruff lint, ruff format) - no modifications
	@$(UV) run mypy src/
	@$(UV) run ruff check src/ tests/
	@$(UV) run ruff format --check src/ tests/

format: ## Auto-fix lint and format issues (runs ruff check --fix and ruff format)
	@$(UV) run ruff check --fix src/ tests/
	@$(UV) run ruff format src/ tests/

clean: ## Deep clean temporary files and virtual environment
	rm -rf .venv
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf .benchmarks/
	rm -rf .coverage
	rm -rf coverage.xml
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

## -- Docker Commands --

docker-build: ## Build the Docker image
	@echo "Building Docker image..."
	@docker compose build
	@echo ""
	@echo "✓ Build complete!"
	@echo ""
	@echo "Run agents using: bin/whaagent.sh <agent-name> [args]"
	@echo "Example: bin/whaagent.sh news -i 'What is the latest in AI?'"
	@echo "Example: bin/whaagent.sh -v developer -i 'Explain the project structure'"
	@echo ""
	@echo "See bin/whaagent.sh --help for more information"

docker-clean: ## Remove Docker containers, images, and volumes
	@echo "Cleaning up Docker resources..."
	@docker compose down -v 2>/dev/null || true
	@docker rmi agents-whaagent 2>/dev/null || true
	@echo "✓ Cleanup complete!"

## -- Build Commands --

build: ## Build wheel and sdist packages
	@$(UV) build
	@echo ""
	@echo "✓ Build complete!"
	@echo "Packages are in dist/"
	@ls -la dist/ 2>/dev/null || true

build-clean: ## Remove build artifacts
	rm -rf dist/
	rm -rf build/
	rm -rf src/*.egg-info
	@echo "✓ Build artifacts cleaned!"

## -- Release Commands --

release: ## Release whaagent package (usage: make release VERSION=1.0.0-alpha)
	@if [ -z "$(VERSION)" ]; then echo "Error: VERSION is required (e.g., VERSION=1.0.0-alpha)"; exit 1; fi
	@./scripts/release.sh $(VERSION)

## -- Gateway Commands --

gateway-build: ## Build Go gateway binary
	@cd gateway && go build -o whaagent-gateway .
	@echo "✓ Gateway binary: gateway/whaagent-gateway"

gateway-test: ## Run Go gateway tests
	@cd gateway && go test ./... -v

## -- DO Deploy --

deploy-do: ## Full deploy on Digital Ocean (run on droplet: build + restart + toolbox)
	@./scripts/deploy-do.sh deploy

deploy-do-stop: ## Stop all services on Digital Ocean
	@./scripts/deploy-do.sh stop

deploy-do-logs: ## Tail logs on Digital Ocean (optional: gateway, api)
	@./scripts/deploy-do.sh logs $(filter-out $@,$(MAKECMDGOALS))
