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
  ANALYTICS_FOUNDATION_BASE_URL
  AF_READ_TRENDS_PATH
  AF_READ_WAFERS_PATH
  AF_CREATE_WORKSPACE_PATH
  AF_APPLY_FILTERS_PATH
  AF_REGISTER_DATASET_PATH
  AF_GET_REGISTRATION_PATH
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
  -e AGENT_RUNTIME_REPOSITORY_ROOT=/app \
  -e AGENT_RUNTIME_DATABASE_PATH=/app/runtime-data/conversations.sqlite \
  -e MODEL_GATEWAY_ENDPOINT \
  -e MODEL_GATEWAY_MODEL \
  -e MODEL_GATEWAY_API_KEY \
  -e ANALYTICS_FOUNDATION_BASE_URL \
  -e AF_READ_TRENDS_PATH \
  -e AF_READ_WAFERS_PATH \
  -e AF_CREATE_WORKSPACE_PATH \
  -e AF_APPLY_FILTERS_PATH \
  -e AF_REGISTER_DATASET_PATH \
  -e AF_GET_REGISTRATION_PATH \
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
