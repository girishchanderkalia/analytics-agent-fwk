#!/usr/bin/env bash
set -euo pipefail

# Local deployment for manual UI testing. Run from Git Bash:
#   scripts/local-deploy.sh [--agents "<pkg-dir>[;<pkg-dir>...]"] [--no-browser]
# --agents registers extra agent packages alongside the four OPO Monitoring
# agents; each needs a distinct id/version.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTRA_AGENTS=""
OPEN_BROWSER=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agents) EXTRA_AGENTS="${2:?--agents requires a value}"; shift 2 ;;
    --no-browser) OPEN_BROWSER=false; shift ;;
    -h|--help) sed -n '4,7p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
  esac
done

cd "$ROOT_DIR"
export SLICE13K_ROOT_DIR="$ROOT_DIR"
export BFF_PORT="${BFF_PORT:-8080}"
RUN_DIR="${SLICE13K_RUN_DIR:-$ROOT_DIR/.run/slice13k}"

has_service_deps() {
  [[ -n "$1" && -x "$1" ]] && "$1" -c 'import sys, uvicorn, fastapi, httpx, langgraph; raise SystemExit(sys.version_info < (3, 13))' >/dev/null 2>&1
}

# Same managed venv as the integration tests, so a prior test run is reused.
venv_python="$RUN_DIR/venv/Scripts/python.exe"
if has_service_deps "${PYTHON_BIN:-}"; then
  :
elif has_service_deps "$venv_python"; then
  PYTHON_BIN="$venv_python"
else
  base_python=""
  for candidate in "${PYTHON_BIN:-}" "${VIRTUAL_ENV:+$VIRTUAL_ENV/Scripts/python.exe}" "${CONDA_PREFIX:+$CONDA_PREFIX/python.exe}" "$(command -v python || true)"; do
    if [[ -n "$candidate" && -x "$candidate" ]] && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 13))' >/dev/null 2>&1; then
      base_python="$candidate"
      break
    fi
  done
  if [[ -z "$base_python" ]]; then
    echo "ERROR: Python 3.13+ is required. Set PYTHON_BIN to a compatible interpreter." >&2
    exit 1
  fi
  mkdir -p "$RUN_DIR"
  [[ -x "$venv_python" ]] || "$base_python" -m venv "$(cygpath -w "$RUN_DIR/venv")"
  echo "Installing service dependencies into $RUN_DIR/venv"
  "$venv_python" -m pip install --disable-pip-version-check \
    -r "$ROOT_DIR/agent-framework/agent-runtime/requirements.txt" \
    -r "$ROOT_DIR/agent-framework/agent-runtime/requirements-langgraph.txt" \
    -r "$ROOT_DIR/analytics-foundation/analytics-foundation-api/requirements.txt" \
    -e "$ROOT_DIR/analytics-foundation/analytics-foundation-client" \
    -e "$ROOT_DIR/analytics-foundation/analytics-foundation-mcp" \
    -e "$ROOT_DIR/agent-framework/integration-tests"
  PYTHON_BIN="$venv_python"
fi
export PYTHON_BIN

packages="$(cygpath -w "$ROOT_DIR/agents/opo-analysis-agent-v1");$(cygpath -w "$ROOT_DIR/agents/opo-analysis-agent-v4")"
if [[ -n "$EXTRA_AGENTS" ]]; then
  IFS=';' read -r -a extra_dirs <<< "$EXTRA_AGENTS"
  for dir in "${extra_dirs[@]}"; do
    [[ -z "$dir" ]] && continue
    if [[ ! -f "$dir/agent-definition.md" ]]; then
      echo "ERROR: Not an agent package (missing agent-definition.md): $dir" >&2
      exit 1
    fi
    packages+=";$(cygpath -w "$(cd "$dir" && pwd)")"
  done
fi
export AGENT_MARKDOWN_PACKAGES="$packages"

echo "Stopping any previously started services..."
"$ROOT_DIR/scripts/stop-services.sh" >/dev/null 2>&1 || true

stop_all() {
  echo
  echo "Stopping local deployment..."
  "$ROOT_DIR/scripts/stop-services.sh" || true
}
trap stop_all INT TERM EXIT

echo "Registering agent packages: $AGENT_MARKDOWN_PACKAGES"
SLICE13K_MANAGED=true "$ROOT_DIR/scripts/start-services.sh"

UI_URL="http://127.0.0.1:$BFF_PORT/"
echo
echo "Registered agents:"
curl -fsS "http://127.0.0.1:${RUNTIME_PORT:-8000}/v1/applications/${AGENT_APPLICATION_ID:-opo-monitoring}/agents" || echo "  (could not list agents)"
echo
echo
echo "OPO Monitoring UI: $UI_URL"
echo "Logs:              $ROOT_DIR/.run/slice13k/logs"
echo "Press Ctrl+C to stop all services."

if [[ "$OPEN_BROWSER" == true ]]; then
  start "" "$UI_URL" 2>/dev/null || true
fi

while true; do
  sleep 3600
done
