#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-application-agent-runtime}"
IMAGE_TAG="${IMAGE_TAG:-local}"

PYTHONPATH="$(pwd):$(pwd)/agent-framework/agent-runtime" python -m pytest agent-framework/tests -q --tb=short

docker build \
  --file Dockerfile \
  --tag "${IMAGE_NAME}:${IMAGE_TAG}" \
  .

echo "Built ${IMAGE_NAME}:${IMAGE_TAG}"
