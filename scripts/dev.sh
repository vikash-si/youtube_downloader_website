#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-start}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
PID_FILE="$ROOT_DIR/.backend.pid"
LOG_FILE="$ROOT_DIR/.backend.log"

setup() {
    command -v python3 >/dev/null || { echo "Python 3.10+ is required."; exit 1; }
    python3 -m venv "$ROOT_DIR/.venv"
    "$VENV_PYTHON" -m pip install --upgrade pip
    "$VENV_PYTHON" -m pip install -r "$ROOT_DIR/backend/requirements.txt"

    command -v ffmpeg >/dev/null || echo "Warning: FFmpeg was not found on PATH."
    command -v deno >/dev/null || echo "Warning: Deno was not found on PATH."
    echo "Setup complete."
}

stop() {
    if [[ ! -f "$PID_FILE" ]]; then
        echo "Backend is not running."
        return
    fi

    local pid
    pid="$(<"$PID_FILE")"
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        echo "Stopped backend process $pid."
    else
        echo "Removed stale backend PID file."
    fi
    rm -f "$PID_FILE"
}

start() {
    if [[ ! -x "$VENV_PYTHON" ]]; then
        echo "Virtual environment not found. Running setup first."
        setup
    fi

    if [[ -f "$PID_FILE" ]] && kill -0 "$(<"$PID_FILE")" 2>/dev/null; then
        echo "Backend is already running (PID $(<"$PID_FILE"))."
        return
    fi
    rm -f "$PID_FILE"
    nohup "$VENV_PYTHON" backend/main.py >"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
    echo "Backend started at http://127.0.0.1:8000 (PID $(<"$PID_FILE"))."
    echo "Logs: $LOG_FILE"
}

case "$ACTION" in
    setup) setup ;;
    start) start ;;
    stop) stop ;;
    restart) stop; start ;;
    *)
        echo "Usage: ./scripts/dev.sh {setup|start|stop|restart}"
        exit 1
        ;;
esac
