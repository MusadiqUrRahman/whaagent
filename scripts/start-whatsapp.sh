#!/bin/bash
# whaagent WhatsApp Agent Startup Script
#
# Usage:
#   bash start-whatsapp.sh jean
#   bash start-whatsapp.sh le

set -euo pipefail

TENANT="${1:?}"
PROJECT_DIR="$HOME/projects/test-whaagent/whaagent"
LOG_DIR="$HOME/.local/share/whaagent/logs"
HOST="0.0.0.0"
PORT="8000"

mkdir -p "$LOG_DIR"

API_LOG="$LOG_DIR/api-${TENANT}.log"
GATEWAY_LOG="$LOG_DIR/gateway-${TENANT}.log"
PID_FILE="$PROJECT_DIR/.whaagent-pids-${TENANT}"

is_running() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null; }

read_pids() {
    if [ -f "$PID_FILE" ]; then
        API_PID=$(sed -n '1p' "$PID_FILE")
        GW_PID=$(sed -n '2p' "$PID_FILE")
    fi
}

save_pids() {
    echo "$API_PID" > "$PID_FILE"
    echo "$GW_PID" >> "$PID_FILE"
}

stop() {
    read_pids
    if is_running "${API_PID:-}"; then kill "$API_PID" 2>/dev/null; echo "Stopped API"; fi
    if is_running "${GW_PID:-}"; then kill "$GW_PID" 2>/dev/null; echo "Stopped gateway"; fi
    rm -f "$PID_FILE"
}

start() {
    stop

    echo "=== Starting WhatsApp Agent ${TENANT} at $(date) ==="

    # API
    echo "Starting API on ${HOST}:${PORT}..."
    nohup "$PROJECT_DIR/.venv/bin/whaagent" serve --host "$HOST" --port "$PORT" >> "$API_LOG" 2>&1 &
    API_PID=$!
    disown $API_PID
    echo "API started (PID: $API_PID)"

    # Wait for API health
    for i in $(seq 1 30); do
        curl -sf "http://127.0.0.1:${PORT}/health" > /dev/null 2>&1 && break
        sleep 1
    done

    # Gateway
    echo "Starting gateway..."
    nohup "$PROJECT_DIR/gateway/whaagent-gateway" >> "$GATEWAY_LOG" 2>&1 &
    GW_PID=$!
    disown $GW_PID
    echo "Gateway started (PID: $GW_PID)"

    save_pids
    echo "Running: API=$API_PID Gateway=$GW_PID"
    echo "Health: http://localhost:${PORT}/health"
}

case "${2:-}" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 1; start ;;
    status)
        read_pids
        if is_running "${API_PID:-}"; then echo "API: RUNNING (PID: $API_PID)"; else echo "API: STOPPED"; fi
        if is_running "${GW_PID:-}"; then echo "Gateway: RUNNING (PID: $GW_PID)"; else echo "Gateway: STOPPED"; fi
        ;;
    logs)
        tail -f "$API_LOG" "$GATEWAY_LOG" ;;
    *) echo "Usage: $0 {tenant} {start|stop|restart|status|logs}" ;;
esac