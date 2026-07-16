#!/usr/bin/env bash
# whaagent service manager for DigitalOcean droplet
# Manages both the Go gateway and Python API server
#
# Usage:
#   ./whaagent-service.sh start    - Start both services
#   ./whaagent-service.sh stop     - Stop both services
#   ./whaagent-service.sh restart  - Restart both services
#   ./whaagent-service.sh status   - Check if services are running
#   ./whaagent-service.sh logs     - Tail logs from both services

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────
PROJECT_DIR="${PROJECT_DIR:-$HOME/projects/test-whaagent/whaagent}"
GATEWAY_DIR="${PROJECT_DIR}/gateway"
LOG_DIR="${LOG_DIR:-$HOME/.local/share/whaagent/logs}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

GATEWAY_LOG="${LOG_DIR}/gateway.log"
API_LOG="${LOG_DIR}/api.log"
PID_FILE="${PROJECT_DIR}/.whaagent-pids"

# ── Helpers ────────────────────────────────────────────────────────

log_info()  { echo -e "\033[0;32m[INFO]\033[0m $1"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m $1"; }
log_error() { echo -e "\033[0;31m[ERROR]\033[0m $1"; }

mkdir -p "$LOG_DIR"

is_running() {
    local pid="$1"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

read_pids() {
    if [ -f "$PID_FILE" ]; then
        GATEWAY_PID=$(sed -n '1p' "$PID_FILE")
        API_PID=$(sed -n '2p' "$PID_FILE")
    fi
}

save_pids() {
    echo "$GATEWAY_PID" > "$PID_FILE"
    echo "$API_PID" >> "$PID_FILE"
}

# ── Commands ───────────────────────────────────────────────────────

do_start() {
    read_pids

    # Check if already running
    if is_running "${GATEWAY_PID:-}" && is_running "${API_PID:-}"; then
        log_warn "Already running (gateway=$GATEWAY_PID, api=$API_PID)"
        return 0
    fi

    log_info "Starting whaagent services..."

    # Build gateway if binary doesn't exist or source is newer
    if [ ! -f "${GATEWAY_DIR}/whaagent-gateway" ] || \
       find "${GATEWAY_DIR}" -name '*.go' -newer "${GATEWAY_DIR}/whaagent-gateway" -print -quit | grep -q .; then
        log_info "Building Go gateway..."
        (cd "$GATEWAY_DIR" && go build -o whaagent-gateway .) || log_error "Failed to build gateway"
    fi

    # Start Python API FIRST (gateway needs it to send QR codes)
    if ! is_running "${API_PID:-}"; then
        log_info "Starting Python API on ${HOST}:${PORT}..."
        nohup whaagent serve --host "$HOST" --port "$PORT" > "$API_LOG" 2>&1 &
        API_PID=$!
        log_info "API started (PID: $API_PID)"

        # Wait for API to be ready before starting gateway
        log_info "Waiting for API to be ready..."
        for i in $(seq 1 30); do
            if curl -sf "http://127.0.0.1:${PORT}/health" > /dev/null 2>&1; then
                log_info "API is ready"
                break
            fi
            if [ "$i" -eq 30 ]; then
                log_error "API failed to start within 30 seconds"
                cat "$API_LOG"
                return 1
            fi
            sleep 1
        done
    fi

    # Start Go gateway (needs API running to send QR codes)
    if ! is_running "${GATEWAY_PID:-}"; then
        log_info "Starting Go gateway..."
        nohup "${GATEWAY_DIR}/whaagent-gateway" > "$GATEWAY_LOG" 2>&1 &
        GATEWAY_PID=$!
        log_info "Gateway started (PID: $GATEWAY_PID)"
    fi

    save_pids

    echo ""
    log_info "Services running:"
    echo "  Gateway:  PID $GATEWAY_PID (log: $GATEWAY_LOG)"
    echo "  API:      PID $API_PID (log: $API_LOG)"
    echo "  QR pages: http://$(hostname -I | awk '{print $1}'):${PORT}/qr/{tenant_id}/page"
    echo "  Health:   http://$(hostname -I | awk '{print $1}'):${PORT}/health"
}

do_stop() {
    read_pids

    log_info "Stopping whaagent services..."

    if is_running "${API_PID:-}"; then
        kill "$API_PID" 2>/dev/null && log_info "API stopped (PID: $API_PID)" || true
    fi

    if is_running "${GATEWAY_PID:-}"; then
        kill "$GATEWAY_PID" 2>/dev/null && log_info "Gateway stopped (PID: $GATEWAY_PID)" || true
    fi

    rm -f "$PID_FILE"
    log_info "All services stopped"
}

do_restart() {
    do_stop
    sleep 1
    do_start
}

do_status() {
    read_pids

    local all_ok=true

    if is_running "${GATEWAY_PID:-}"; then
        log_info "Gateway: RUNNING (PID: $GATEWAY_PID)"
    else
        log_error "Gateway: STOPPED"
        all_ok=false
    fi

    if is_running "${API_PID:-}"; then
        log_info "API:     RUNNING (PID: $API_PID)"
    else
        log_error "API:     STOPPED"
        all_ok=false
    fi

    if [ "$all_ok" = true ]; then
        echo ""
        echo "  Health: curl http://localhost:${PORT}/health"
        echo "  Agents: curl -H 'X-API-Key: YOUR_KEY' http://localhost:${PORT}/api/v1/agents"
    fi
}

do_logs() {
    local target="${1:-all}"

    case "$target" in
        gateway)
            tail -f "$GATEWAY_LOG"
            ;;
        api)
            tail -f "$API_LOG"
            ;;
        all|*)
            tail -f "$GATEWAY_LOG" "$API_LOG"
            ;;
    esac
}

# ── Main ───────────────────────────────────────────────────────────

case "${1:-}" in
    start)   do_start ;;
    stop)    do_stop ;;
    restart) do_restart ;;
    status)  do_status ;;
    logs)    do_logs "${2:-all}" ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs [gateway|api]}"
        echo ""
        echo "Commands:"
        echo "  start    Start both services (gateway + API)"
        echo "  stop     Stop both services"
        echo "  restart  Restart both services"
        echo "  status   Check if services are running"
        echo "  logs     Tail logs (optional: gateway, api, all)"
        exit 1
        ;;
esac
