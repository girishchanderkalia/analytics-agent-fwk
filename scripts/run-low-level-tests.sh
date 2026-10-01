#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_PYTHON="${BASE_PYTHON:-python}"
MVN="${MVN:-mvn}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "$1" >&2
    exit 1
  fi
}

require_command "$MVN"
require_command java

is_python_313_or_newer() {
  "$1" -c 'import sys; raise SystemExit(sys.version_info < (3, 13))' >/dev/null 2>&1
}

if [[ -n "${PYTHON:-}" ]]; then
  TEST_PYTHON="$PYTHON"
elif command -v cygpath >/dev/null 2>&1; then
  DEFAULT_VENV_PYTHON="$ROOT_DIR/.venv/Scripts/python.exe"
  TEST_VENV="$ROOT_DIR/.venv-low-level-tests"
  TEST_PYTHON="$TEST_VENV/Scripts/python.exe"
else
  DEFAULT_VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
  TEST_VENV="$ROOT_DIR/.venv-low-level-tests"
  TEST_PYTHON="$TEST_VENV/bin/python"
fi

if [[ -z "${PYTHON:-}" ]]; then
  if [[ -x "$DEFAULT_VENV_PYTHON" ]] && is_python_313_or_newer "$DEFAULT_VENV_PYTHON"; then
    TEST_PYTHON="$DEFAULT_VENV_PYTHON"
  elif [[ -x "$TEST_PYTHON" ]]; then
    if ! is_python_313_or_newer "$TEST_PYTHON"; then
      printf 'The existing low-level test environment is older than Python 3.13: %s\n' "$TEST_PYTHON" >&2
      printf 'Set PYTHON to a Python 3.13+ interpreter to use it directly.\n' >&2
      exit 1
    fi
  else
    require_command "$BASE_PYTHON"
    if ! is_python_313_or_newer "$BASE_PYTHON"; then
      printf 'BASE_PYTHON must be Python 3.13 or newer; found an incompatible interpreter.\n' >&2
      printf 'Set BASE_PYTHON to the Python 3.13 executable, or set PYTHON to use it directly.\n' >&2
      exit 1
    fi
    "$BASE_PYTHON" -m venv "$TEST_VENV"
  fi
fi

if ! is_python_313_or_newer "$TEST_PYTHON"; then
  printf 'Python 3.13 or newer is required by the OPO test packages.\n' >&2
  exit 1
fi

printf '\n== Install Python test dependencies ==\n'
"$TEST_PYTHON" -m pip install \
  -r "$ROOT_DIR/requirements.txt" \
  -r "$ROOT_DIR/agent-framework/agent-runtime/requirements.txt" \
  -r "$ROOT_DIR/agent-framework/agent-runtime/requirements-langgraph.txt" \
  -r "$ROOT_DIR/analytics-foundation/analytics-foundation-api/requirements.txt"

to_python_path() {
  local paths="$1"
  local converted
  local separator

  if command -v cygpath >/dev/null 2>&1; then
    converted="$(cygpath -wp "$paths")"
  else
    converted="$paths"
  fi

  separator="$("$TEST_PYTHON" -c 'import os; print(os.pathsep)')"
  if [[ -n "${PYTHONPATH:-}" ]]; then
    converted="${converted}${separator}${PYTHONPATH}"
  fi
  printf '%s' "$converted"
}

run_python_suite() {
  local label="$1"
  local package="$2"
  local import_paths="$3"

  printf '\n== %s ==\n' "$label"
  (
    cd "$ROOT_DIR/$package"
    export PYTHONPATH="$(to_python_path "$import_paths")"
    "$TEST_PYTHON" "$ROOT_DIR/run_pytest.py" tests -q
  )
}

run_python_suite \
  'Analytics Foundation client' \
  'analytics-foundation/analytics-foundation-client' \
  "$ROOT_DIR/analytics-foundation/analytics-foundation-client/src"

run_python_suite \
  'Analytics Foundation API' \
  'analytics-foundation/analytics-foundation-api' \
  "$ROOT_DIR/analytics-foundation/analytics-foundation-api"

run_python_suite \
  'Analytics Foundation MCP' \
  'analytics-foundation/analytics-foundation-mcp' \
  "$ROOT_DIR/analytics-foundation/analytics-foundation-mcp/src:$ROOT_DIR/analytics-foundation/analytics-foundation-client/src:$ROOT_DIR/agent-framework/agent-runtime"

run_python_suite \
  'Agent framework components' \
  'agent-framework' \
  "$ROOT_DIR:$ROOT_DIR/agent-framework/agent-runtime"

printf '\n== OPO Java BFF ==\n'
(
  cd "$ROOT_DIR/app-ui/opo-monitoring/opo-monitoring-service"
  "$MVN" test
)

printf '\nAll low-level test suites passed. No live services or integration tests were run.\n'