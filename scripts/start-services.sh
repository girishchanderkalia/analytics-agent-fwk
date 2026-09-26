#!/usr/bin/env bash
set -euo pipefail

# Slice 13K local launcher. Run from the repository root in Git Bash.
ROOT_DIR="${SLICE13K_ROOT_DIR:-$(pwd)}"
RUN_DIR="${SLICE13K_RUN_DIR:-$ROOT_DIR/.run/slice13k}"
LOG_DIR="$RUN_DIR/logs"
PID_DIR="$RUN_DIR/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

JAVA_HOME="${JAVA_HOME:-/c/Program Files/Java/jdk-25.0.1}"
JAVA_EXE="$JAVA_HOME/bin/java.exe"
if [[ ! -x "$JAVA_EXE" ]]; then
  echo "ERROR: Java executable not found: $JAVA_EXE" >&2
  exit 1
fi
export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  :
elif [[ -n "${VIRTUAL_ENV:-}" && -x "$VIRTUAL_ENV/Scripts/python.exe" ]]; then
  PYTHON_BIN="$VIRTUAL_ENV/Scripts/python.exe"
elif [[ -x "$ROOT_DIR/.venv/Scripts/python.exe" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/Scripts/python.exe"
elif [[ -x "$(cd "$ROOT_DIR/.." && pwd)/.venv/Scripts/python.exe" ]]; then
  PYTHON_BIN="$(cd "$ROOT_DIR/.." && pwd)/.venv/Scripts/python.exe"
else
  PYTHON_BIN="$(command -v python || true)"
fi
if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: No executable Python interpreter found." >&2
  exit 1
fi
PYTHON_BIN="$(cd "$(dirname "$PYTHON_BIN")" && pwd)/$(basename "$PYTHON_BIN")"

MAVEN_BIN="${MAVEN_BIN:-$(command -v mvn || true)}"
MAVEN_SETTINGS="${MAVEN_SETTINGS:-$HOME/.m2/settings.xml}"
if [[ -z "$MAVEN_BIN" || ! -x "$MAVEN_BIN" ]]; then
  echo "ERROR: Maven executable not found." >&2
  exit 1
fi
if [[ ! -f "$MAVEN_SETTINGS" ]]; then
  echo "ERROR: Maven settings not found: $MAVEN_SETTINGS" >&2
  exit 1
fi

FOUNDATION_PORT="${FOUNDATION_PORT:-8200}"
FOUNDATION_MCP_PORT="${FOUNDATION_MCP_PORT:-8100}"
OPO_CAPABILITY_PORT="${OPO_CAPABILITY_PORT:-8300}"
RUNTIME_PORT="${RUNTIME_PORT:-8000}"
BFF_PORT="${BFF_PORT:-8080}"

FOUNDATION_START_CMD="${FOUNDATION_START_CMD:-\"$PYTHON_BIN\" -m uvicorn foundation_api.app:app --host 127.0.0.1 --port $FOUNDATION_PORT}"
FOUNDATION_MCP_START_CMD="${FOUNDATION_MCP_START_CMD:-\"$PYTHON_BIN\" -m uvicorn analytics_foundation_mcp.app:app --host 127.0.0.1 --port $FOUNDATION_MCP_PORT}"
OPO_CAPABILITY_START_CMD="${OPO_CAPABILITY_START_CMD:-\"$PYTHON_BIN\" -m uvicorn opo_capability_service.app:app --host 127.0.0.1 --port $OPO_CAPABILITY_PORT}"
RUNTIME_START_CMD="${RUNTIME_START_CMD:-\"$PYTHON_BIN\" -m uvicorn runtime_api.main:app --host 127.0.0.1 --port $RUNTIME_PORT}"
BFF_START_CMD="${BFF_START_CMD:-\"$MAVEN_BIN\" -s \"$MAVEN_SETTINGS\" -DskipTests spring-boot:run}"

export ANALYTICS_FOUNDATION_BASE_URL="${ANALYTICS_FOUNDATION_BASE_URL:-http://127.0.0.1:$FOUNDATION_PORT}"
export ANALYTICS_FOUNDATION_MCP_URL="${ANALYTICS_FOUNDATION_MCP_URL:-http://127.0.0.1:$FOUNDATION_MCP_PORT/mcp}"
export OPO_CAPABILITY_MCP_URL="${OPO_CAPABILITY_MCP_URL:-http://127.0.0.1:$OPO_CAPABILITY_PORT/mcp}"
export RUNTIME_SERVICE_BASE_URL="${RUNTIME_SERVICE_BASE_URL:-http://127.0.0.1:$RUNTIME_PORT}"
export SERVER_PORT="$BFF_PORT"

# Windows Python uses semicolon-separated PYTHONPATH entries.
export PYTHONPATH="${ROOT_DIR}/analytics-foundation/analytics-foundation-api;${ROOT_DIR}/analytics-foundation/analytics-foundation/analytics-foundation-mcp/src;${ROOT_DIR}/app-ui/opo-monitoring/opo-monitoring-service/app-ui/opo-monitoring/opo-monitoring-service/opo-capability-service/src;${ROOT_DIR}/app-ui/opo-monitoring/opo-monitoring-service/app-ui/opo-monitoring/opo-monitoring-service/opo-deterministic-logic/src;${ROOT_DIR}/analytics-foundation/analytics-foundation/analytics-foundation-client/src;${ROOT_DIR}/agent-framework/agent-runtime${PYTHONPATH:+;$PYTHONPATH}"

echo "Using Java:   $JAVA_EXE"
echo "Using Python: $PYTHON_BIN"
echo "Using Maven:  $MAVEN_BIN"

required=(analytics-foundation-api analytics-foundation-mcp opo-capability-service agent-runtime app-ui/opo-monitoring)
for relative in "${required[@]}"; do
  if [[ ! -d "$ROOT_DIR/$relative" ]]; then
    echo "ERROR: Required directory not found: $ROOT_DIR/$relative" >&2
    exit 1
  fi
done

pid_is_running() {
  local file="$1" pid
  [[ -f "$file" ]] || return 1
  pid="$(tr -d '\r\n ' < "$file")"
  [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null
}

start_service() {
  local name="$1" directory="$2" command="$3"
  local pid_file="$PID_DIR/$name.pid" log_file="$LOG_DIR/$name.log"
  if pid_is_running "$pid_file"; then
    echo "$name already running with PID $(cat "$pid_file")"
    return
  fi
  rm -f "$pid_file"
  echo "Starting $name"
  echo "  directory: $directory"
  echo "  log:       $log_file"
  (
    cd "$directory"
    exec bash -c "$command"
  ) >"$log_file" 2>&1 &
  local pid=$!
  echo "$pid" > "$pid_file"
  sleep 1
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$pid_file"
    echo "ERROR: $name exited during startup" >&2
    tail -n 100 "$log_file" >&2 || true
    exit 1
  fi
}

wait_for_get() {
  local name="$1" url="$2" log_file="$3"
  echo "Waiting for $name at $url"
  if ! "$PYTHON_BIN" - "$url" <<'PYGET'
import sys, time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
url = sys.argv[1]
last = None
for _ in range(60):
    try:
        with urlopen(url, timeout=2) as response:
            if 200 <= response.status < 300:
                raise SystemExit(0)
    except (HTTPError, URLError, OSError) as error:
        last = error
        time.sleep(1)
raise SystemExit(f"Endpoint unavailable: {url}: {last}")
PYGET
  then
    echo "ERROR: $name did not become ready" >&2
    tail -n 100 "$log_file" >&2 || true
    exit 1
  fi
  echo "$name is available"
}

wait_for_mcp() {
  local name="$1" url="$2" log_file="$3"
  echo "Waiting for $name at $url"
  if ! "$PYTHON_BIN" - "$url" <<'PYMCP'
import json, sys, time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
url = sys.argv[1]
data = json.dumps({"jsonrpc":"2.0","id":"startup","method":"tools/list","params":{}}).encode()
last = None
for _ in range(60):
    try:
        request = Request(url, data=data, headers={"Content-Type":"application/json"}, method="POST")
        with urlopen(request, timeout=2) as response:
            body = json.loads(response.read().decode())
            if response.status == 200 and "result" in body:
                raise SystemExit(0)
    except (HTTPError, URLError, OSError, ValueError) as error:
        last = error
        time.sleep(1)
raise SystemExit(f"MCP endpoint unavailable: {url}: {last}")
PYMCP
  then
    echo "ERROR: $name did not become ready" >&2
    tail -n 100 "$log_file" >&2 || true
    exit 1
  fi
  echo "$name is available"
}

start_service "analytics-foundation" "$ROOT_DIR/analytics-foundation/analytics-foundation-api" "$FOUNDATION_START_CMD"
wait_for_get "Analytics Foundation API" "http://127.0.0.1:$FOUNDATION_PORT/health" "$LOG_DIR/analytics-foundation.log"
start_service "analytics-foundation-mcp" "$ROOT_DIR/analytics-foundation/analytics-foundation-mcp" "$FOUNDATION_MCP_START_CMD"
wait_for_mcp "Analytics Foundation MCP" "http://127.0.0.1:$FOUNDATION_MCP_PORT/mcp" "$LOG_DIR/analytics-foundation-mcp.log"
start_service "opo-capability" "$ROOT_DIR/app-ui/opo-monitoring/opo-monitoring-service/opo-capability-service" "$OPO_CAPABILITY_START_CMD"
wait_for_get "OPO capability service" "http://127.0.0.1:$OPO_CAPABILITY_PORT/ready" "$LOG_DIR/opo-capability.log"
start_service "agent-runtime" "$ROOT_DIR/agent-framework/agent-runtime" "$RUNTIME_START_CMD"
wait_for_get "Agent Runtime" "http://127.0.0.1:$RUNTIME_PORT/health" "$LOG_DIR/agent-runtime.log"
start_service "opo-bff" "$ROOT_DIR/app-ui/opo-monitoring" "$BFF_START_CMD"
wait_for_get "OPO BFF" "http://127.0.0.1:$BFF_PORT/actuator/health" "$LOG_DIR/opo-bff.log"

echo
printf '%s\n' "All Slice 13K services are available." "Logs: $LOG_DIR" "Stop: scripts/stop-slice-13k-services.sh"
echo
echo "Slice 13K services are running."
echo "Keep this terminal open."
echo "Press Ctrl+C to stop all services."

shutdown_services() {
  echo
  echo "Stopping Slice 13K services..."

  "$ROOT_DIR/scripts/stop-slice-13k-services.sh" \
    >/dev/null 2>&1 \
    || true
}

trap shutdown_services INT TERM EXIT

while true
do
  sleep 3600
done