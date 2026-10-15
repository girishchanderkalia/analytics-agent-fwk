# Shared deployment config parsing for build/build-containers.sh and build/deploy.sh.
# shellcheck shell=bash

# Supported keys and their defaults. See build/local.conf and build/remote.conf.example.
declare -A cfg=(
  [TARGET]="local"
  [IMAGE_TAG]="local"
  [KUBE_CONTEXT]=""
  [INGRESS_HOST]=""
  [INGRESS_NGINX_VERSION]=""
  [REMOTE_HOST]=""
  [REMOTE_USER]=""
  [REMOTE_PORT]="22"
  [SSH_IDENTITY_FILE]=""
  [SSH_OPTIONS]=""
  [REMOTE_WORK_DIR]="/tmp/analytics-agent-fwk-images"
  [REMOTE_REGISTRY]=""
  [REMOTE_REGISTRY_PATH]=""
  [REMOTE_IMAGE_TAG]=""
  [PODMAN_CMD]="podman"
  [PODMAN_PUSH_OPTIONS]=""
  [REMOTE_KUBECTL]="kubectl"
  # Env file deploy.sh reads Secret values from; empty = repo-root .env.
  [SECRETS_ENV_FILE]=""
)

all_images=(
  application-agent-runtime
  analytics-foundation-api
  analytics-foundation-mcp
  lanadb-mcp
  opo-monitoring
)

die() { echo "ERROR: $*" >&2; exit 1; }

# Parses KEY=VALUE lines instead of sourcing, so the file cannot run code.
read_config() {
  local file="$1" line key value lineno=0
  [[ -f "$file" ]] || die "Config file not found: $file"
  while IFS= read -r line || [[ -n "$line" ]]; do
    lineno=$((lineno + 1))
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
    [[ "$line" =~ ^[[:space:]]*([A-Z_]+)[[:space:]]*=(.*)$ ]] \
      || die "$file:$lineno: expected KEY=VALUE"
    key="${BASH_REMATCH[1]}"
    value="${BASH_REMATCH[2]}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if [[ "$value" =~ ^\"(.*)\"$ || "$value" =~ ^\'(.*)\'$ ]]; then
      value="${BASH_REMATCH[1]}"
    fi
    [[ -v "cfg[$key]" ]] || die "$file:$lineno: unknown key $key"
    cfg[$key]="$value"
  done <"$file"

  case "${cfg[TARGET]}" in
    local|remote) ;;
    *) die "$file: TARGET must be 'local' or 'remote'" ;;
  esac
  [[ -n "${cfg[IMAGE_TAG]}" ]] || die "$file: IMAGE_TAG must not be empty"
  [[ -z "${cfg[INGRESS_HOST]}" || "${cfg[INGRESS_HOST]}" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ ]] \
    || die "$file: INGRESS_HOST must be a lowercase DNS name"
  [[ -z "${cfg[INGRESS_NGINX_VERSION]}" || "${cfg[INGRESS_NGINX_VERSION]}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
    || die "$file: INGRESS_NGINX_VERSION must look like 1.15.1"
}

# Sets the global images array from a comma-separated list (empty = all images).
select_images() {
  local csv="$1" image
  if [[ -z "$csv" ]]; then
    images=("${all_images[@]}")
    return
  fi
  IFS=',' read -r -a images <<<"$csv"
  for image in "${images[@]}"; do
    [[ " ${all_images[*]} " == *" $image "* ]] || die "Unknown image: $image"
  done
}
