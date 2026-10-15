#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: ./build/deploy.sh [--config FILE] [--images LIST] [--skip-load | --load-only]

Load the images built by build/build-containers.sh into a Kubernetes cluster
and deploy deploy/k8s there. Everything about the target cluster comes from
the config file:

  TARGET=local   The local cluster (Docker Desktop or kind; KUBE_CONTEXT or the
                 current kubectl context). Images are imported straight into
                 each node's containerd; no registry is used. The ingress-nginx
                 controller (INGRESS_NGINX_VERSION) is installed if missing.
  TARGET=remote  A cluster reached through its management node over SSH
                 (key-based authentication). Each image is copied as a tar
                 archive, then loaded, tagged, and pushed to REMOTE_REGISTRY
                 with podman; kubectl runs on the management node.

Options:
  --config FILE   Deployment config (default: build/local.conf). Copy
                  build/remote.conf.example to build/remote.conf for remote.
  --images LIST   Comma-separated subset of images to load and update
                  (default: all). Other Deployments keep their current image.
  --skip-load     Only deploy (config, Secrets, CA bundle, manifests). Remote
                  with empty REMOTE_IMAGE_TAG keeps the deployed images.
  --load-only     Only load images; do not deploy.
  -h, --help      Show this help.

Deploying also creates/updates the Secrets from the repo-root .env (or
SECRETS_ENV_FILE in the config file) when present, and restarts Deployments
whose Secret or ConfigMap changed (and, for TARGET=local, those whose image
was just reloaded under the same tag).
USAGE
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/config.sh
source "$repo_root/build/lib/config.sh"

# Image prefix used by deploy/k8s/kustomization.yaml; rewritten per target.
manifest_registry="registry.example.com"
manifest_tag="latest"
namespace="ai-agent-fwk"

config_file="build/local.conf"
images_csv=""
do_load=true
do_deploy=true

need_value() { (($1 >= 2)) || { echo "Missing value for $2" >&2; exit 2; }; }

while (($#)); do
  case "$1" in
    --config) need_value $# "$1"; config_file="$2"; shift 2 ;;
    --images) need_value $# "$1"; images_csv="$2"; shift 2 ;;
    --skip-load) do_load=false; shift ;;
    --load-only) do_deploy=false; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done
[[ "$do_load" == true || "$do_deploy" == true ]] \
  || die "--skip-load and --load-only cannot be combined"

cd "$repo_root"
read_config "$config_file"
select_images "$images_csv"
target="${cfg[TARGET]}"
tag="${cfg[IMAGE_TAG]}"

# Git Bash would otherwise rewrite container paths such as /host into Windows paths.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

work_dir="$(mktemp -d)"
cleanup_actions=("rm -rf '$work_dir'")
cleanup() {
  local action
  for action in "${cleanup_actions[@]}"; do eval "$action" || true; done
}
trap cleanup EXIT

check_local_images() {
  local image
  command -v docker >/dev/null || die "docker is required"
  for image in "${images[@]}"; do
    docker image inspect "$image:$tag" >/dev/null 2>&1 \
      || die "Local image $image:$tag not found. Run: ./build/build-containers.sh --config $config_file"
  done
}

# ---------------------------------------------------------------- local ----

# kubectl against the local cluster (KUBE_CONTEXT or the current context).
kc() {
  if [[ -n "${cfg[KUBE_CONTEXT]}" ]]; then
    kubectl --context "${cfg[KUBE_CONTEXT]}" "$@"
  else
    kubectl "$@"
  fi
}

setup_local() {
  command -v kubectl >/dev/null || die "kubectl is required"
  kube_context="${cfg[KUBE_CONTEXT]}"
  if [[ -z "$kube_context" ]]; then
    kube_context="$(kubectl config current-context 2>/dev/null)" || die "No current kubectl context"
  fi
  kc get nodes >/dev/null 2>&1 || die "Cannot reach the cluster of kubectl context '$kube_context'"
  echo "Target: local cluster, kubectl context '$kube_context'"
}

# Installs (or upgrades) the ingress-nginx controller that serves the
# ingressClassName: nginx Ingress, and waits until its admission webhook works.
install_ingress_nginx() {
  local version="${cfg[INGRESS_NGINX_VERSION]}" provider=cloud current url
  [[ -n "$version" ]] || return 0
  [[ "$kube_context" == kind-* ]] && provider=kind
  current="$(kc -n ingress-nginx get deploy ingress-nginx-controller \
    -o 'jsonpath={.metadata.labels.app\.kubernetes\.io/version}' 2>/dev/null || true)"
  if [[ "$current" == "$version" ]]; then
    echo "ingress-nginx $version already installed"
    return 0
  fi
  url="https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v${version}/deploy/static/provider/${provider}/deploy.yaml"
  echo "Installing ingress-nginx $version (${provider} provider)${current:+, replacing $current}"
  # The admission Jobs are immutable; remove the old ones before an upgrade.
  [[ -n "$current" ]] && kc -n ingress-nginx delete job \
    -l app.kubernetes.io/component=admission-webhook --ignore-not-found
  curl -fsSL "$url" | kc apply -f - || die "Failed to install ingress-nginx from $url"
  # The controller mounts the webhook cert created by the admission Jobs (which
  # are TTL-deleted), so its rollout also covers the webhook being usable.
  kc -n ingress-nginx rollout status deploy/ingress-nginx-controller --timeout=300s \
    || die "ingress-nginx controller did not become ready"
}

load_local() {
  if [[ "$kube_context" == kind-* ]] && command -v kind >/dev/null; then
    local image
    for image in "${images[@]}"; do
      echo "== kind load $image:$tag"
      kind load docker-image "$image:$tag" --name "${kube_context#kind-}"
    done
    return
  fi

  # Docker Desktop (kind based) and similar clusters do not share the Docker
  # image store, so import the images into containerd on every node through a
  # short-lived privileged helper pod.
  local nodes node pod
  nodes="$(kc get nodes -o jsonpath='{.items[*].metadata.name}')"
  [[ -n "$nodes" ]] || die "No nodes found in context '$kube_context'"
  for node in $nodes; do
    pod="image-loader-$$-$RANDOM"
    cleanup_actions+=("kc -n kube-system delete pod '$pod' --ignore-not-found --wait=false >/dev/null")
    echo "Starting helper pod $pod on node $node"
    kc apply -f - >/dev/null <<YAML
apiVersion: v1
kind: Pod
metadata:
  name: $pod
  namespace: kube-system
spec:
  nodeName: $node
  hostPID: true
  restartPolicy: Never
  tolerations: [{operator: Exists}]
  containers:
  - name: loader
    image: busybox:1.37
    command: ["sleep", "3600"]
    securityContext: {privileged: true}
    volumeMounts: [{name: host, mountPath: /host}]
  volumes: [{name: host, hostPath: {path: /}}]
YAML
    kc -n kube-system wait --for=condition=Ready "pod/$pod" --timeout=180s >/dev/null
    kc -n kube-system exec "$pod" -- chroot /host ctr --version >/dev/null 2>&1 \
      || die "Node $node does not expose containerd 'ctr'; load images manually"

    local image
    for image in "${images[@]}"; do
      echo "== $image:$tag -> node $node"
      docker save "$image:$tag" \
        | kc -n kube-system exec -i "$pod" -- \
            chroot /host ctr -n k8s.io images import --all-platforms - >/dev/null
    done
    kc -n kube-system delete pod "$pod" --wait=false >/dev/null
  done
}

# --------------------------------------------------------------- remote ----

setup_remote() {
  command -v ssh >/dev/null || die "ssh is required"
  [[ -n "${cfg[REMOTE_HOST]}" ]] || die "REMOTE_HOST is required in $config_file"
  [[ -n "${cfg[REMOTE_REGISTRY]}" ]] || die "REMOTE_REGISTRY is required in $config_file"
  [[ -z "${cfg[INGRESS_NGINX_VERSION]}" ]] \
    || die "INGRESS_NGINX_VERSION is only supported for TARGET=local; the remote cluster provides its own ingress controller"
  cfg[REMOTE_REGISTRY]="${cfg[REMOTE_REGISTRY]%/}"
  cfg[REMOTE_REGISTRY_PATH]="${cfg[REMOTE_REGISTRY_PATH]#/}"
  cfg[REMOTE_REGISTRY_PATH]="${cfg[REMOTE_REGISTRY_PATH]%/}"

  ssh_target="${cfg[REMOTE_HOST]}"
  [[ -n "${cfg[REMOTE_USER]}" ]] && ssh_target="${cfg[REMOTE_USER]}@$ssh_target"
  # ServerAlive* keeps the connection alive (and detects a dead one quickly)
  # during the long, mostly-silent image transfers; without it, idle VPN/
  # firewall hops can drop the connection mid-copy, breaking the local
  # "docker save | gzip | ssh" pipe (seen as SIGPIPE / "pipe is being closed").
  ssh_cmd=(ssh -p "${cfg[REMOTE_PORT]}" -o BatchMode=yes -o ConnectTimeout=15 \
    -o ServerAliveInterval=30 -o ServerAliveCountMax=6)
  [[ -n "${cfg[SSH_IDENTITY_FILE]}" ]] && ssh_cmd+=(-i "${cfg[SSH_IDENTITY_FILE]}")
  if [[ -n "${cfg[SSH_OPTIONS]}" ]]; then
    local -a extra
    read -r -a extra <<<"${cfg[SSH_OPTIONS]}"
    ssh_cmd+=("${extra[@]}")
  fi
  ssh_cmd+=("$ssh_target")
  remote_kubectl="$(printf '%q' "${cfg[REMOTE_KUBECTL]}")"

  # A fresh tag per load so nodes pull the new images (IfNotPresent). When only
  # deploying without a configured tag, the currently deployed images are kept.
  remote_tag="${cfg[REMOTE_IMAGE_TAG]}"
  if [[ -z "$remote_tag" && "$do_load" == true ]]; then
    remote_tag="$(date +%Y%m%d%H%M%S)"
  fi

  echo "Target: remote cluster via $ssh_target (registry ${cfg[REMOTE_REGISTRY]}, tag ${remote_tag:-<deployed>})"
  "${ssh_cmd[@]}" true || die "Cannot reach $ssh_target over SSH with key-based authentication"
}

# Run a bash script on the management node; arguments are safely quoted.
remote_bash() {
  local script="$1"; shift
  local quoted="" arg
  for arg in "$@"; do quoted+=" $(printf '%q' "$arg")"; done
  "${ssh_cmd[@]}" "bash -s --$quoted" <<<"$script"
}

remote_image_ref() {
  local name="$1"
  local path="${cfg[REMOTE_REGISTRY]}"
  [[ -n "${cfg[REMOTE_REGISTRY_PATH]}" ]] && path+="/${cfg[REMOTE_REGISTRY_PATH]}"
  echo "$path/$name"
}

load_remote() {
  remote_bash '
set -euo pipefail
command -v "${1##* }" >/dev/null || { echo "${1##* } not found on management node" >&2; exit 1; }
command -v gzip >/dev/null || { echo "gzip not found on management node" >&2; exit 1; }
mkdir -p "$2"' "${cfg[PODMAN_CMD]}" "${cfg[REMOTE_WORK_DIR]}"

  local image tar_name target_ref
  for image in "${images[@]}"; do
    tar_name="$image-$tag.tar"
    target_ref="$(remote_image_ref "$image"):$remote_tag"
    transfer_image "$image" "$tar_name" "$target_ref"
  done
}

# Copies, loads, tags and pushes one image; retried since the copy step is a
# long-lived "docker save | gzip | ssh" pipe that can be killed mid-transfer
# by a transient network/VPN blip (surfaces as SIGPIPE or a stuck pipe).
transfer_image() {
  local image="$1" tar_name="$2" target_ref="$3" attempt
  for attempt in 1 2 3; do
    echo "== $image:$tag -> $ssh_target:${cfg[REMOTE_WORK_DIR]}/$tar_name${attempt:+ (attempt $attempt/3)}"
    if docker save "$image:$tag" | gzip -1 \
         | "${ssh_cmd[@]}" "gzip -dc > $(printf '%q' "${cfg[REMOTE_WORK_DIR]}/$tar_name")" \
       && echo "   podman load / tag / push $target_ref" \
       && remote_bash '
set -euo pipefail
podman_cmd=$1 tar_file=$2 source_ref=$3 target_ref=$4 push_opts=$5
read -r -a push_args <<<"$push_opts"
trap '\''rm -f "$tar_file"'\'' EXIT
load_output=$($podman_cmd load < "$tar_file")
echo "   $load_output"
loaded=$(printf "%s\n" "$load_output" | sed -n "s/^Loaded image[^:]*: *//p" | tail -n 1)
# Docker short names are loaded under localhost/ by podman.
loaded=${loaded:-localhost/$source_ref}
$podman_cmd tag "$loaded" "$target_ref"
$podman_cmd push ${push_args[@]+"${push_args[@]}"} "$target_ref"
' "${cfg[PODMAN_CMD]}" "${cfg[REMOTE_WORK_DIR]}/$tar_name" "$image:$tag" \
         "$target_ref" "${cfg[PODMAN_PUSH_OPTIONS]}"
    then
      return 0
    fi
    [[ "$attempt" == 3 ]] && die "Failed to transfer/push $image after 3 attempts"
    echo "   Transfer of $image failed, retrying..." >&2
  done
}

# --------------------------------------------------------------- deploy ----

# kubectl in the target cluster (locally, or on the management node).
tk() {
  if [[ "$target" == local ]]; then
    kc "$@"
  else
    local quoted="" arg
    for arg in "$@"; do quoted+=" $(printf '%q' "$arg")"; done
    "${ssh_cmd[@]}" "$remote_kubectl$quoted"
  fi
}

# Prints the image of an existing Deployment (same name as the image), or nothing.
deployed_image() {
  tk -n "$namespace" get "deploy/$1" \
    -o 'jsonpath={.spec.template.spec.containers[0].image}' 2>/dev/null || true
}

# Image reference for a newly loaded image, or empty when no new tag is known.
new_image_ref() {
  if [[ "$target" == local ]]; then
    echo "$1:$tag"
  elif [[ -n "$remote_tag" ]]; then
    echo "$(remote_image_ref "$1"):$remote_tag"
  fi
}

render_manifests() {
  local output="$1" expr=() image ref
  for image in "${all_images[@]}"; do
    ref=""
    [[ " ${images[*]} " == *" $image "* ]] && ref="$(new_image_ref "$image")"
    # Images not selected (or without a new tag) keep what is deployed now.
    [[ -n "$ref" ]] || ref="$(deployed_image "$image")"
    if [[ -z "$ref" ]]; then
      [[ "$target" == local ]] || die "deploy/$image is not deployed yet; load it first (set REMOTE_IMAGE_TAG or include it in --images)"
      ref="$image:$tag"
    fi
    echo "   $image -> $ref"
    expr+=(-e "s#image: ${manifest_registry}/${image}:${manifest_tag}\$#image: ${ref}#")
  done
  if [[ -n "${cfg[INGRESS_HOST]}" ]]; then
    echo "   ingress host -> ${cfg[INGRESS_HOST]}"
    expr+=(-e "s#^\([[:space:]]*- host: \).*#\1${cfg[INGRESS_HOST]}#")
  fi
  kubectl kustomize deploy/k8s | sed "${expr[@]}" >"$output"
  if grep -q "image: ${manifest_registry}/" "$output"; then
    die "Rendered manifests still reference ${manifest_registry}; check deploy/k8s/kustomization.yaml"
  fi
}

# Secret keys pulled out of the single secrets env file, per k8s Secret.
runtime_secret_keys=(MODEL_GATEWAY_API_KEY)
lanadb_secret_keys=(LANADB_JDBC_URL LANADB_USERNAME LANADB_PASSWORD)

# Prints the last uncommented "KEY=..." line for each requested key found in
# a file (same toggle-by-comment convention .env already uses).
extract_env_keys() {
  local file="$1"; shift
  local key
  for key in "$@"; do
    grep -E "^${key}=" "$file" | tail -n 1
  done
}

# Writes Secret manifests from the gitignored secrets env file (repo-root
# .env by default) without printing values.
render_secrets() {
  local output="$1" found=false
  : >"$output"
  local env_file="${cfg[SECRETS_ENV_FILE]:-.env}"
  if [[ ! -f "$env_file" ]]; then
    echo "WARNING: secrets env file '$env_file' not found; Secrets left unchanged" >&2
    return 1
  fi
  # Relative to cwd (repo root), not under $work_dir: native kubectl.exe
  # under Git Bash cannot resolve absolute MSYS paths like /tmp/tmp.XXXX as
  # a --from-env-file argument (MSYS_NO_PATHCONV=1 is set for this script).
  local runtime_file=".deploy-runtime.secret.env.tmp" lanadb_file=".deploy-lanadb.secret.env.tmp"
  cleanup_actions+=("rm -f '$runtime_file' '$lanadb_file'")
  extract_env_keys "$env_file" "${runtime_secret_keys[@]}" >"$runtime_file"
  extract_env_keys "$env_file" "${lanadb_secret_keys[@]}" >"$lanadb_file"
  if [[ -s "$runtime_file" ]]; then
    kubectl create secret generic application-agent-runtime-secrets -n "$namespace" \
      --from-env-file="$runtime_file" --dry-run=client -o yaml >>"$output"
    echo "---" >>"$output"
    found=true
  fi
  if [[ -s "$lanadb_file" ]]; then
    # Refuse the common mistake of pushing a local dev database into the
    # shared remote cluster's Secret (values come from the same file used
    # for local runs); leave the existing remote Secret untouched instead.
    if [[ "$target" == remote ]] && grep -Eq "^LANADB_JDBC_URL=.*(127\.0\.0\.1|localhost)" "$lanadb_file"; then
      echo "WARNING: LANADB_JDBC_URL in '$env_file' points at localhost/127.0.0.1;" \
        "refusing to deploy it to the remote cluster's lanadb-mcp-secrets." \
        "Comment out the local LANADB_* block and uncomment the remote one, then retry." >&2
    else
      kubectl create secret generic lanadb-mcp-secrets -n "$namespace" \
        --from-env-file="$lanadb_file" --dry-run=client -o yaml >>"$output"
      found=true
    fi
  fi
  [[ "$found" == true ]]
}

deployments=(
  analytics-foundation-api
  lanadb-mcp
  analytics-foundation-mcp
  application-agent-runtime
  opo-monitoring
)

# Applies the Istio VirtualService and confirms it actually exists afterward,
# retrying a few times before giving up; "kubectl apply" succeeding is not
# sufficient proof on its own (observed dropped silently by a namespace
# delete/recreate race), and without this route the UI is unreachable.
apply_virtualservice() {
  local name="vcp-ingress-ai-agent-fwk-opo-monitoring" attempt
  for attempt in 1 2 3; do
    tk apply -f - <deploy/k8s/virtualservice.yaml
    tk -n "$namespace" get "virtualservice/$name" >/dev/null 2>&1 && return 0
    echo "WARNING: virtualservice/$name missing right after apply (attempt $attempt/3), retrying..." >&2
    sleep 3
  done
  die "virtualservice/$name does not exist after 3 apply attempts; the UI Ingress route is broken"
}

deploy() {
  local manifests="$work_dir/manifests.yaml" secrets="$work_dir/secrets.yaml"
  local apply_output d
  local -A restart=()
  command -v kubectl >/dev/null || die "kubectl is required to render manifests"
  echo "Deploying to namespace $namespace:"
  render_manifests "$manifests"
  [[ "$target" == local ]] && install_ingress_nginx
  # Feed files via stdin: Windows kubectl.exe cannot resolve MSYS /tmp paths.
  tk apply -f - <deploy/k8s/namespace.yaml
  if render_secrets "$secrets"; then
    apply_output="$(tk apply -f - <"$secrets" 2>&1 | tee /dev/stderr)"
    # Pods only read their Secret at startup, so roll them when it changed.
    # (CA bundle changes roll the runtime automatically through the hashed
    # ConfigMap name.)
    grep -Eq "^secret/application-agent-runtime-secrets (created|configured)" <<<"$apply_output" \
      && restart[application-agent-runtime]=1
    grep -Eq "^secret/lanadb-mcp-secrets (created|configured)" <<<"$apply_output" \
      && restart[lanadb-mcp]=1
  fi
  local missing_secrets=()
  for d in application-agent-runtime-secrets lanadb-mcp-secrets; do
    tk -n "$namespace" get secret "$d" >/dev/null 2>&1 || missing_secrets+=("$d")
  done
  if ((${#missing_secrets[@]})); then
    echo "WARNING: Secret(s) ${missing_secrets[*]} missing; their Deployments will fail to" \
      "start (CreateContainerConfigError) until created - see deploy/README.md" >&2
  fi
  # Stream apply output as it happens: under 'set -e' a failing apply aborts
  # the script at the command-substitution assignment, so a plain "$(...)"
  # capture would silently discard everything already applied before that.
  apply_output="$(tk apply -f - <"$manifests" 2>&1 | tee /dev/stderr)"
  # Istio VirtualService: only remote clusters are expected to run Istio
  # (local Docker Desktop/kind clusters lack the CRD, so applying it there
  # would fail the whole deploy). This is the UI's only Ingress route, and
  # "kubectl apply" reporting success has been observed to not be enough
  # (e.g. a namespace delete/recreate race can silently drop it), so verify
  # it actually exists afterward and retry before failing loudly.
  [[ "$target" == remote ]] && apply_virtualservice
  # Pods read env-style ConfigMaps/Secrets only at startup, and a local reload
  # keeps the same <name>:<IMAGE_TAG> reference, so restart what changed.
  # This also covers TARGET=remote with a static REMOTE_IMAGE_TAG (e.g.
  # "latest"): render_manifests then emits the same image ref as before, so
  # "kubectl apply" sees no Deployment diff and would otherwise never
  # restart the pods, leaving the old image running despite a fresh push.
  for d in "${deployments[@]}"; do
    if grep -Eq "^configmap/$d-config (created|configured)" <<<"$apply_output"; then
      restart[$d]=1
    fi
    if [[ "$do_load" == true && " ${images[*]} " == *" $d "* ]]; then
      restart[$d]=1
    fi
  done
  for d in "${deployments[@]}"; do
    [[ -n "${restart[$d]:-}" ]] && tk -n "$namespace" rollout restart "deploy/$d"
  done
  for d in "${deployments[@]}"; do
    tk -n "$namespace" rollout status "deploy/$d" --timeout=300s || rollout_failed "$d"
  done
  tk -n "$namespace" get pods
  echo "OPO Monitoring UI: http://$(tk -n "$namespace" get ingress opo-monitoring -o 'jsonpath={.spec.rules[0].host}')/"
}

# Surfaces the actual pod failure (e.g. a missing Secret) instead of leaving
# only the generic "rollout status" timeout/NotFound error.
rollout_failed() {
  local d="$1"
  echo "---- deploy/$d did not become ready; pod status and events: ----" >&2
  tk -n "$namespace" get pods -l "app.kubernetes.io/name=$d" >&2 || true
  tk -n "$namespace" describe pods -l "app.kubernetes.io/name=$d" 2>&1 \
    | grep -A20 '^Events:' >&2 || true
  exit 1
}

# ----------------------------------------------------------------- main ----

if [[ "$target" == local ]]; then setup_local; else setup_remote; fi

if [[ "$do_load" == true ]]; then
  check_local_images
  if [[ "$target" == local ]]; then load_local; else load_remote; fi
fi

[[ "$do_deploy" == true ]] && deploy

echo "Done."