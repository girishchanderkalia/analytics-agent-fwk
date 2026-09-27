#!/usr/bin/env bash
set -euo pipefail

# Browser tests only. The e2e entry point handles toolchain checks, service
# startup, the venv, and teardown; this just narrows the selection.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT_DIR/scripts/run-e2e-tests.sh" --ui-only "$@"
