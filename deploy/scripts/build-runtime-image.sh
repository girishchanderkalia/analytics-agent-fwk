#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-application-agent-runtime}"
IMAGE_TAG="${IMAGE_TAG:-local}"

python -m pytest tests -q --tb=short

docker build \
  --file Dockerfile \
  --tag "${IMAGE_NAME}:${IMAGE_TAG}" \
  .

echo "Built ${IMAGE_NAME}:${IMAGE_TAG}"
