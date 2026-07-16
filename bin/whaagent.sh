#!/usr/bin/env bash

# whaagent.sh - Docker wrapper for WhaAgent CLI
# Usage: bin/whaagent.sh [-v|--verbose] [--env-file <path>] <agent-command> [args...]
# Example: bin/whaagent.sh developer -i "Explain this codebase"
# Example: bin/whaagent.sh -v news -i "What's the latest tech news?"
# Example: bin/whaagent.sh --env-file /path/to/.env chef -i "I have eggs"

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get project root (parent of bin/)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    echo "Please start Docker and try again"
    exit 1
fi

# Check if docker compose is available
if ! docker compose version >/dev/null 2>&1; then
    echo -e "${RED}Error: docker compose is not available${NC}"
    echo "Please install Docker Compose and try again"
    exit 1
fi

# Parse flags
VERBOSE=""
ENV_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -v|--verbose)
            VERBOSE="--verbose"
            shift
            ;;
        --env-file)
            if [[ -z "$2" ]]; then
                echo -e "${RED}Error: --env-file requires a path argument${NC}"
                exit 1
            fi
            ENV_FILE="$2"
            shift 2
            ;;
        *)
            break
            ;;
    esac
done

# Validate env file if provided
if [[ -n "$ENV_FILE" ]] && [[ ! -f "$ENV_FILE" ]]; then
    echo -e "${RED}Error: env file not found: $ENV_FILE${NC}"
    exit 1
fi

# Check if any arguments provided
if [[ $# -eq 0 ]]; then
    echo -e "${YELLOW}Usage: bin/whaagent.sh [-v|--verbose] [--env-file <path>] <agent-command> [args...]${NC}"
    echo ""
    echo "Examples:"
    echo "  bin/whaagent.sh list"
    echo "  bin/whaagent.sh news -i \"What's the latest in AI?\""
    echo "  bin/whaagent.sh -v developer -i \"Explain the project structure\""
    echo "  bin/whaagent.sh --env-file /path/to/.env developer -i \"Explain project\""
    echo "  bin/whaagent.sh developer --input \"Explain project\" --timeout 120"
    echo ""
    echo "Available agents:"
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm whaagent \
        uv run whaagent list 2>/dev/null || echo "  (run 'make docker-build' first)"
    exit 0
fi

# Build command
CMD_ARGS=("$@")

# Add verbose flag if set
if [[ -n "$VERBOSE" ]]; then
    # Insert verbose flag after the agent name (first argument)
    AGENT_NAME="${CMD_ARGS[0]}"
    REST_ARGS=("${CMD_ARGS[@]:1}")
    CMD_ARGS=("$AGENT_NAME" "$VERBOSE" "${REST_ARGS[@]}")
fi

# Run command in Docker
echo -e "${BLUE}Running:${NC} whaagent ${CMD_ARGS[*]}"
echo ""

cd "$PROJECT_ROOT"

# Resolve env file: use provided path, or fall back to project root .env
if [[ -z "$ENV_FILE" ]] && [[ -f "$PROJECT_ROOT/.env" ]]; then
    ENV_FILE="$PROJECT_ROOT/.env"
fi

# Mount env file into container at /app/.env so load_dotenv() picks it up
VOLUME_ARGS=()
if [[ -n "$ENV_FILE" ]]; then
    VOLUME_ARGS=(-v "$(realpath "$ENV_FILE"):/app/.env:ro")
fi

docker compose run --rm "${VOLUME_ARGS[@]}" whaagent \
    uv run whaagent "${CMD_ARGS[@]}"

EXIT_CODE=$?

# Show log location on success
if [[ $EXIT_CODE -eq 0 ]]; then
    echo ""
    echo -e "${GREEN}✓ Command completed successfully${NC}"
    echo -e "${BLUE}Logs:${NC} $PROJECT_ROOT/logs/agent.log"
else
    echo ""
    echo -e "${RED}✗ Command failed with exit code $EXIT_CODE${NC}"
    echo -e "${BLUE}Check logs:${NC} $PROJECT_ROOT/logs/agent.log"
fi

exit $EXIT_CODE
