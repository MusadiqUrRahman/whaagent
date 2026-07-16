#!/bin/bash
# whaagent Full Deploy Script
#
# Stops, pulls, builds, and starts all services.
#
# Usage:
#   bash deploy.sh              # full deploy (pull + build + start)
#   bash deploy.sh status       # show service status
#   bash deploy.sh stop         # stop all services
#   bash deploy.sh restart      # restart without pulling/building
#   bash deploy.sh logs         # tail all logs

set -euo pipefail

# --- Paths (adjust if needed) ---
whaagent_DIR="$HOME/projects/test-whaagent/whaagent"
TOOLKIT_DIR="$HOME/whaagent-toolkit"
LOG_DIR="$HOME/.local/share/whaagent/logs"
HOST="0.0.0.0"
PORT="8000"

mkdir -p "$LOG_DIR"

# --- PID files ---
TOOLKIT_PID_FILE="$TOOLKIT_DIR/.toolbox.pid"
PID_FILE="$whaagent_DIR/.whaagent-pids"

# --- Logging ---
API_LOG="$LOG_DIR/api-$(basename "$whaagent_DIR").log"
GATEWAY_LOG="$LOG_DIR/gateway-$(basename "$whaagent_DIR").log"
TOOLKIT_LOG="$LOG_DIR/toolbox.log"

# --- Helpers ---
is_running() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null; }

read_pids() {
    TOOLKIT_PID=""
    API_PID=""
    GW_PID=""
    [ -f "$TOOLKIT_PID_FILE" ] && TOOLKIT_PID=$(cat "$TOOLKIT_PID_FILE")
    if [ -f "$PID_FILE" ]; then
        API_PID=$(sed -n '1p' "$PID_FILE")
        GW_PID=$(sed -n '2p' "$PID_FILE")
    fi
}

save_pids() {
    echo "$API_PID" > "$PID_FILE"
    echo "$GW_PID" >> "$PID_FILE"
    echo "$TOOLKIT_PID" > "$TOOLKIT_PID_FILE"
}

stop_all() {
    read_pids
    local stopped=0

    echo "Stopping services..."

    # Kill by PID file first
    if is_running "${API_PID:-}";     then kill "$API_PID"      2>/dev/null && echo "  API     (PID $API_PID) stopped"; stopped=1; fi
    if is_running "${GW_PID:-}";      then kill "$GW_PID"       2>/dev/null && echo "  Gateway (PID $GW_PID) stopped"; stopped=1; fi
    if is_running "${TOOLKIT_PID:-}"; then kill "$TOOLKIT_PID"  2>/dev/null && echo "  Toolbox (PID $TOOLKIT_PID) stopped"; stopped=1; fi

    # Kill any orphaned processes (started outside this script)
    if pkill -f "whaagent-gateway"   2>/dev/null; then echo "  Gateway (orphaned) stopped"; stopped=1; fi
    if pkill -f "whaagent serve"     2>/dev/null; then echo "  API     (orphaned) stopped"; stopped=1; fi
    if pkill -f "toolbox-server"     2>/dev/null; then echo "  Toolbox (orphaned) stopped"; stopped=1; fi

    # Wait for ports to free up
    sleep 1

    if [ "$stopped" -eq 0 ]; then
        echo "  (nothing was running)"
    fi

    rm -f "$PID_FILE" "$TOOLKIT_PID_FILE"
}

# --- Pull ---
pull() {
    echo "--- Pulling whaagent ---"
    cd "$whaagent_DIR"
    git pull
    echo "--- Pulling whaagent-toolkit ---"
    cd "$TOOLKIT_DIR"
    git pull
}

# --- Build ---
build() {
    echo "--- Installing whaagent dependencies ---"
    cd "$whaagent_DIR"
    uv sync

    # DNS resolution check (non-fatal diagnostic)
    echo "--- Checking DNS resolution ---"
    if host api.firecrawl.dev >/dev/null 2>&1; then
        echo "  DNS OK: api.firecrawl.dev resolves."
    else
        echo "WARNING: DNS resolution for api.firecrawl.dev failed."
        echo "  Consider adding reliable DNS resolvers to /etc/resolv.conf:"
        echo "    nameserver 8.8.8.8"
        echo "    nameserver 1.1.1.1"
    fi

    # Install Playwright Chromium browser only if missing (needed by Crawl4AI Stage 1)
    # Non-fatal: Stage 1 (Crawl4AI) fails gracefully; Stages 2-3 (Firecrawl, Archive.ph) still work.
    # Override PLAYWRIGHT_BROWSERS_PATH to store browsers on a different disk (e.g. a mounted volume).
    export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$whaagent_DIR/.playwright-browsers}"
    if ! ls "$PLAYWRIGHT_BROWSERS_PATH"/chromium* >/dev/null 2>&1; then
        echo "--- Installing Playwright Chromium browser ---"
        if uv run playwright install --with-deps chromium; then
            echo "  Playwright Chromium installed successfully."
        else
            echo "WARNING: Playwright install failed. Stage 1 (Crawl4AI) will not work."
            echo "  Stages 2 (Firecrawl) and 3 (Archive.ph) will still function."
            echo "  Common fixes: increase disk space, check network connectivity."
        fi
    else
        echo "--- Playwright Chromium already installed ---"
    fi

    echo "--- Installing toolkit dependencies ---"
    cd "$TOOLKIT_DIR"
    uv sync

    echo "--- Building Go gateway ---"
    cd "$whaagent_DIR/gateway"
    go build -o whaagent-gateway .
}

# --- Start ---
start_all() {
    echo "=== Starting all services at $(date) ==="

    # 1. Toolbox (MCP) — must be up before API
    echo "Starting Toolbox..."
    cd "$TOOLKIT_DIR"
    nohup uv run toolbox-server >> "$TOOLKIT_LOG" 2>&1 &
    TOOLKIT_PID=$!
    disown $TOOLKIT_PID

    # Wait for toolbox to accept connections (SSE endpoint holds connection open,
    # so just check that the port responds within 1s — can take up to 20s)
    echo "  (waiting for toolbox to start, up to ~20s...)"
    for i in $(seq 1 15); do
        curl -sf -m 1 "http://127.0.0.1:8080/sse" -o /dev/null 2>&1 && break || true
        sleep 1
    done
    if is_running "$TOOLKIT_PID"; then
        echo "Toolbox ready (PID $TOOLKIT_PID)"
    else
        echo "WARNING: Toolbox not running after 15s"
    fi

    # 2. API
    echo "Starting API on ${HOST}:${PORT}..."
    cd "$whaagent_DIR"
    nohup .venv/bin/whaagent serve --host "$HOST" --port "$PORT" >> "$API_LOG" 2>&1 &
    API_PID=$!
    disown $API_PID

    # Wait for API health
    for i in $(seq 1 30); do
        curl -sf "http://127.0.0.1:${PORT}/health" > /dev/null 2>&1 && break
        sleep 1
    done
    if curl -sf "http://127.0.0.1:${PORT}/health" > /dev/null 2>&1; then
        echo "API ready (PID $API_PID)"
        echo "  (warming up Playwright browser in background...)"
    else
        echo "WARNING: API not responding after 30s"
    fi

    # 3. Gateway
    echo "Starting Gateway..."
    LOG_LEVEL=info nohup "$whaagent_DIR/gateway/whaagent-gateway" >> "$GATEWAY_LOG" 2>&1 &
    GW_PID=$!
    disown $GW_PID
    echo "Gateway started (PID $GW_PID)"

    save_pids
    echo ""
    echo "=== All services running ==="
    echo "  Toolbox: $TOOLKIT_PID  → http://localhost:8080/health"
    echo "  API:     $API_PID      → http://localhost:${PORT}/health"
    echo "  Gateway: $GW_PID"
    echo "  Logs:    $LOG_DIR/"
}

# --- Status ---
show_status() {
    read_pids
    echo "--- Service Status ---"
    if is_running "${TOOLKIT_PID:-}"; then echo "Toolbox: RUNNING (PID $TOOLKIT_PID)"; else echo "Toolbox: STOPPED"; fi
    if is_running "${API_PID:-}";     then echo "API:     RUNNING (PID $API_PID)";     else echo "API:     STOPPED"; fi
    if is_running "${GW_PID:-}";      then echo "Gateway: RUNNING (PID $GW_PID)";      else echo "Gateway: STOPPED"; fi
}

# --- Main ---
case "${1:-}" in
    status)  show_status ;;
    stop)    stop_all ;;
    start)   start_all ;;
    restart) stop_all; sleep 1; start_all ;;
    logs)    tail -f "$TOOLKIT_LOG" "$API_LOG" "$GATEWAY_LOG" ;;
    pull)    pull ;;
    build)   build ;;
    '')      stop_all; pull; build; start_all ;;
    *)       echo "Usage: $0 [start|stop|restart|status|logs|pull|build]" ;;
esac
