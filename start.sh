#!/usr/bin/env bash
# Launch backend (uvicorn :8000) and frontend (next :3000) together.
# Usage: ./start.sh        — start both
#        ./start.sh stop   — kill anything on :3000 / :8000

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

kill_ports() {
  local pids
  pids="$(lsof -ti:3000,8000 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "Killing existing processes on :3000 / :8000 → $pids"
    echo "$pids" | xargs kill -9 2>/dev/null || true
  fi
}

if [[ "${1:-}" == "stop" ]]; then
  kill_ports
  exit 0
fi

kill_ports

BACKEND_LOG="$LOG_DIR/backend_run.log"
FRONTEND_LOG="$LOG_DIR/frontend_run.log"

echo "Starting backend → $BACKEND_LOG"
(
  cd "$ROOT/backend"
  python3 -m uvicorn api.main:app --reload --port 8000
) >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo "Starting frontend → $FRONTEND_LOG"
(
  cd "$ROOT/frontend"
  npm run dev
) >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

cleanup() {
  echo
  echo "Shutting down (backend=$BACKEND_PID frontend=$FRONTEND_PID)..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  kill_ports
}
trap cleanup INT TERM EXIT

echo
echo "Backend  → http://localhost:8000  (pid $BACKEND_PID)"
echo "Frontend → http://localhost:3000  (pid $FRONTEND_PID)"
echo "Logs     → $LOG_DIR/"
echo "Ctrl-C to stop both."
echo

wait
