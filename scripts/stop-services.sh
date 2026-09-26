#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${SLICE13K_ROOT_DIR:-$(pwd)}"
RUN_DIR="${SLICE13K_RUN_DIR:-$ROOT_DIR/.run/slice13k}"
PID_DIR="$RUN_DIR/pids"

stop_one() {
  local name="$1" file="$2" pid
  [[ -f "$file" ]] || return 0
  pid="$(tr -d '\r\n ' < "$file")"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    echo "Stopping $name (PID $pid)"
    kill "$pid" 2>/dev/null || true
    for _ in {1..10}; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
      echo "Force stopping $name (PID $pid)"
      kill -9 "$pid" 2>/dev/null || true
    fi
  else
    echo "Removing stale PID for $name"
  fi
  rm -f "$file"
}

for name in opo-bff agent-runtime opo-capability analytics-foundation-mcp analytics-foundation; do
  stop_one "$name" "$PID_DIR/$name.pid"
done

if [[ -d "$PID_DIR" ]]; then
  find "$PID_DIR" -maxdepth 1 -type f -name '*.pid' -delete
  rm -rf "$PID_DIR"
fi

if [[ "${REMOVE_SLICE13K_LOGS:-false}" == "true" ]]; then
  rm -rf "$RUN_DIR"
else
  echo "Logs retained in: $RUN_DIR/logs"
fi

echo "Slice 13K services stopped and PID files removed"
