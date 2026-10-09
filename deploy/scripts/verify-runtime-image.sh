#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-application-agent-runtime}"
IMAGE_TAG="${IMAGE_TAG:-local}"
CONTAINER_NAME="application-agent-runtime-verify"
HOST_PORT="${HOST_PORT:-18000}"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

required=(
  MODEL_GATEWAY_ENDPOINT
  MODEL_GATEWAY_MODEL
  ANALYTICS_FOUNDATION_MCP_URL
  LANADB_MCP_URL
)

for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "ERROR: ${name} is not set"
    exit 1
  fi
done

mkdir -p runtime-data

docker run --rm -d \
  --name "${CONTAINER_NAME}" \
  -p "${HOST_PORT}:8000" \
  -v "$(pwd)/runtime-data:/app/runtime-data" \
  -e AGENT_RUNTIME_DATABASE_PATH=/app/runtime-data/conversations.sqlite \
  -e MODEL_GATEWAY_ENDPOINT \
  -e MODEL_GATEWAY_MODEL \
  -e MODEL_GATEWAY_API_KEY \
  -e ANALYTICS_FOUNDATION_MCP_URL \
  -e LANADB_MCP_URL \
  "${IMAGE_NAME}:${IMAGE_TAG}"

python - <<PYTHON
import time
from urllib.request import urlopen

url = "http://127.0.0.1:${HOST_PORT}/health"
last_error = None
for _ in range(30):
    try:
        with urlopen(url, timeout=2) as response:
            if response.status == 200:
                print("Runtime health check passed")
                raise SystemExit(0)
    except Exception as exc:
        last_error = exc
        time.sleep(1)
raise SystemExit(f"Runtime health check failed: {last_error}")
PYTHON
