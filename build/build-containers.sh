#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: ./build/build-containers.sh [--config FILE] [--images LIST]

Build the Kubernetes deployment images in the local Docker image store as
<name>:<IMAGE_TAG>, with IMAGE_TAG taken from the deployment config.

Options:
  --config FILE   Deployment config (default: build/local.conf).
                  Use the same file with build/deploy.sh.
  --images LIST   Comma-separated subset of images (default: all):
                  application-agent-runtime, analytics-foundation-api,
                  analytics-foundation-mcp, lanadb-mcp, opo-monitoring
  -h, --help      Show this help.
USAGE
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/config.sh
source "$repo_root/build/lib/config.sh"

config_file="build/remote.conf"
images_csv=""

while (($#)); do
  case "$1" in
    --config|--images)
      (($# >= 2)) || { echo "Missing value for $1" >&2; exit 2; }
      [[ "$1" == --config ]] && config_file="$2" || images_csv="$2"
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

cd "$repo_root"
read_config "$config_file"
select_images "$images_csv"
tag="${cfg[IMAGE_TAG]}"
command -v docker >/dev/null || die "docker is required"

declare -A dockerfile=(
  [application-agent-runtime]="Dockerfile"
  [analytics-foundation-api]="analytics-foundation/analytics-foundation-api/Dockerfile"
  [analytics-foundation-mcp]="analytics-foundation/analytics-foundation-mcp/Dockerfile"
  [lanadb-mcp]="analytics-foundation/lanadb-mcp/Dockerfile"
  [opo-monitoring]="app-ui/opo-monitoring/Dockerfile"
)
declare -A context=(
  [application-agent-runtime]="."
  [analytics-foundation-api]="analytics-foundation/analytics-foundation-api"
  [analytics-foundation-mcp]="."
  [lanadb-mcp]="analytics-foundation/lanadb-mcp"
  [opo-monitoring]="app-ui/opo-monitoring"
)

for image in "${images[@]}"; do
  echo "== Building $image:$tag"
  docker build --file "${dockerfile[$image]}" --tag "$image:$tag" "${context[$image]}"
done
echo "Built: ${images[*]/%/:$tag}"