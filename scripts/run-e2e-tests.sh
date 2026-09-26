#!/usr/bin/env bash
#
# End-to-end test entry point. Runnable directly after a fresh clone, from any
# working directory. Checks the toolchain up front, then hands over to
# run-integration-tests.sh, which creates an isolated virtual environment,
# installs every service dependency, starts the services, runs pytest, and
# stops the services again.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage: scripts/run-e2e-tests.sh [--with-agent] [pytest arguments...]

Options:
  --with-agent   Also run the model-backed chat tests. Requires a working
                 model gateway configuration on the Agent Runtime.
  -h, --help     Show this message.

Examples:
  scripts/run-e2e-tests.sh
  scripts/run-e2e-tests.sh -m deterministic
  scripts/run-e2e-tests.sh --with-agent -q

Prerequisites: Python 3.13 or newer, a JDK, and Maven. Set PYTHON_BIN,
JAVA_HOME, or MAVEN_BIN if any of them are not discoverable on PATH.
USAGE
}

pytest_args=()
for argument in "$@"; do
  case "$argument" in
    --with-agent)
      export RUN_AGENT_E2E=true
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      pytest_args+=("$argument")
      ;;
  esac
done

missing=()

if [[ -z "${JAVA_HOME:-}" ]] && ! command -v java >/dev/null 2>&1; then
  missing+=("Java: install a JDK 21 or newer, or set JAVA_HOME")
fi

if [[ -z "${MAVEN_BIN:-}" ]] && ! command -v mvn >/dev/null 2>&1; then
  missing+=("Maven: install Apache Maven, or set MAVEN_BIN to its executable")
fi

python_found=false
for candidate in \
  "${PYTHON_BIN:-}" \
  "${VIRTUAL_ENV:+$VIRTUAL_ENV/Scripts/python.exe}" \
  "${CONDA_PREFIX:+$CONDA_PREFIX/python.exe}" \
  "$ROOT_DIR/.venv/Scripts/python.exe" \
  "$(command -v python || true)" \
  "$(command -v python3 || true)"; do
  if [[ -n "$candidate" && -x "$candidate" ]] &&
    "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 13))' >/dev/null 2>&1; then
    python_found=true
    break
  fi
done
if [[ "$python_found" != true ]] && ! command -v py >/dev/null 2>&1 &&
  ! command -v conda >/dev/null 2>&1; then
  missing+=("Python 3.13+: install it, or set PYTHON_BIN to a compatible interpreter")
fi

if ((${#missing[@]} > 0)); then
  echo "ERROR: Missing prerequisites:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi

exec "$ROOT_DIR/scripts/run-integration-tests.sh" "${pytest_args[@]}"
