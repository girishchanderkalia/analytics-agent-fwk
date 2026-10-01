#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export SLICE13K_ROOT_DIR="$ROOT_DIR"
source "$ROOT_DIR/scripts/load-env.sh" "$ROOT_DIR/.env"
RUN_DIR="${SLICE13K_RUN_DIR:-$ROOT_DIR/.run/slice13k}"
LAUNCHER_LOG="$RUN_DIR/integration-launcher.log"

if compgen -G "$RUN_DIR/pids/*.pid" >/dev/null; then
  echo "ERROR: Service PID files already exist. Stop those services before running integration tests." >&2
  exit 1
fi

for port in "${FOUNDATION_PORT:-8200}" "${FOUNDATION_MCP_PORT:-8100}" "${RUNTIME_PORT:-8000}" "${BFF_PORT:-8080}"; do
  if (echo > "/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    echo "ERROR: Port $port is already in use. Stop the existing service before running integration tests." >&2
    exit 1
  fi
done

python_compatible() {
  [[ -n "$1" && -x "$1" ]] && "$1" -c 'import sys; raise SystemExit(sys.version_info < (3, 13))' >/dev/null 2>&1
}

base_python="${PYTHON_BIN:-}"
if [[ -n "$base_python" ]] && ! python_compatible "$base_python"; then
  echo "ERROR: PYTHON_BIN must point to Python 3.13 or newer: $base_python" >&2
  exit 1
fi
if [[ -z "$base_python" ]]; then
  for candidate in "${VIRTUAL_ENV:+$VIRTUAL_ENV/Scripts/python.exe}" "${CONDA_PREFIX:+$CONDA_PREFIX/python.exe}" "$ROOT_DIR/.venv/Scripts/python.exe" "$(command -v python || true)"; do
    if python_compatible "$candidate"; then
      base_python="$candidate"
      break
    fi
  done
fi
if [[ -z "$base_python" ]] && command -v py >/dev/null 2>&1; then
  candidate="$(py -3.13 -c 'import sys; print(sys.executable)' 2>/dev/null || true)"
  if [[ -n "$candidate" ]] && python_compatible "$(cygpath -u "$candidate")"; then
    base_python="$(cygpath -u "$candidate")"
  fi
fi
if [[ -z "$base_python" ]] && command -v conda >/dev/null 2>&1; then
  conda_base="$(conda info --base 2>/dev/null || true)"
  if [[ -n "$conda_base" ]]; then
    conda_base="$(cygpath -u "$conda_base")"
    for candidate in "$conda_base"/envs/*/python.exe "$conda_base"/python.exe; do
      if python_compatible "$candidate"; then
        base_python="$candidate"
        break
      fi
    done
  fi
fi
if [[ -z "$base_python" ]]; then
  echo "ERROR: Python 3.13+ is required. Install it or set PYTHON_BIN to a compatible interpreter." >&2
  exit 1
fi

venv_dir="$RUN_DIR/venv"
PYTHON_BIN="$venv_dir/Scripts/python.exe"
mkdir -p "$RUN_DIR"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Creating integration test environment with $base_python"
  "$base_python" -m venv "$(cygpath -w "$venv_dir")"
fi

manifests=(
  "$ROOT_DIR/agent-framework/agent-runtime/requirements.txt"
  "$ROOT_DIR/agent-framework/agent-runtime/requirements-langgraph.txt"
  "$ROOT_DIR/analytics-foundation/analytics-foundation-api/requirements.txt"
  "$ROOT_DIR/analytics-foundation/analytics-foundation-client/pyproject.toml"
  "$ROOT_DIR/analytics-foundation/analytics-foundation-mcp/pyproject.toml"
  "$ROOT_DIR/agent-framework/integration-tests/pyproject.toml"
)
dependency_hash="$(sha256sum "${manifests[@]}" | sha256sum | cut -d ' ' -f 1)"
stamp="$venv_dir/.integration-deps"
if [[ ! -f "$stamp" || "$(<"$stamp")" != "$dependency_hash" ]] || ! "$PYTHON_BIN" -c 'import uvicorn, fastapi, httpx, pytest, langgraph' >/dev/null 2>&1; then
  echo "Installing integration test dependencies into $venv_dir"
  "$PYTHON_BIN" -m pip install --disable-pip-version-check \
    -r "${manifests[0]}" -r "${manifests[1]}" -r "${manifests[2]}" \
    -e "$ROOT_DIR/analytics-foundation/analytics-foundation-client" \
    -e "$ROOT_DIR/analytics-foundation/analytics-foundation-mcp" \
    -e "$ROOT_DIR/agent-framework/integration-tests"
  "$PYTHON_BIN" -m playwright install chromium
  printf '%s\n' "$dependency_hash" > "$stamp"
fi
export PYTHON_BIN

SLICE13K_MANAGED=true "$ROOT_DIR/scripts/start-services.sh" >"$LAUNCHER_LOG" 2>&1 &
launcher_pid=$!

cleanup() {
  "$ROOT_DIR/scripts/stop-services.sh"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Starting services (launcher log: $LAUNCHER_LOG)"
ready=false
for ((attempt = 0; attempt < 600; attempt++)); do
  if grep -q '^OPO BFF is available$' "$LAUNCHER_LOG"; then
    ready=true
    break
  fi
  if ! kill -0 "$launcher_pid" 2>/dev/null; then
    echo "ERROR: Service launcher exited before all services were ready." >&2
    tail -n 100 "$LAUNCHER_LOG" >&2
    exit 1
  fi
  sleep 1
done

if [[ "$ready" != true ]]; then
  echo "ERROR: Timed out waiting for services to become ready." >&2
  tail -n 100 "$LAUNCHER_LOG" >&2
  exit 1
fi

echo "Running integration tests"
cd "$ROOT_DIR/agent-framework/integration-tests"
"$PYTHON_BIN" -m pytest -q "$@"