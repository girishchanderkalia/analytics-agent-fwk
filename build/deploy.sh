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

Deploying also creates/updates the Secrets from deploy/k8s/*.secret.env when
present, and restarts Deployments whose Secret or ConfigMap changed (and, for
TARGET=local, those whose image was just reloaded under the same tag).
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
  ssh_cmd=(ssh -p "${cfg[REMOTE_PORT]}" -o BatchMode=yes -o ConnectTimeout=15)
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
    echo "== $image:$tag -> $ssh_target:${cfg[REMOTE_WORK_DIR]}/$tar_name"
    docker save "$image:$tag" | gzip -1 \
      | "${ssh_cmd[@]}" "gzip -dc > $(printf '%q' "${cfg[REMOTE_WORK_DIR]}/$tar_name")"

    echo "   podman load / tag / push $target_ref"
    remote_bash '
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

# Writes Secret manifests from gitignored env files without printing values.
render_secrets() {
  local output="$1" found=false
  : >"$output"
  if [[ -f deploy/k8s/runtime.secret.env ]]; then
    kubectl create secret generic application-agent-runtime-secrets -n "$namespace" \
      --from-env-file=deploy/k8s/runtime.secret.env --dry-run=client -o yaml >>"$output"
    echo "---" >>"$output"
    found=true
  fi
  if [[ -f deploy/k8s/lanadb.secret.env ]]; then
    kubectl create secret generic lanadb-mcp-secrets -n "$namespace" \
      --from-env-file=deploy/k8s/lanadb.secret.env --dry-run=client -o yaml >>"$output"
    found=true
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

deploy() {
  local manifests="$work_dir/manifests.yaml" secrets="$work_dir/secrets.yaml"
  local apply_output d
  command -v kubectl >/dev/null || die "kubectl is required to render manifests"
  echo "Deploying to namespace $namespace:"
  render_manifests "$manifests"
  [[ "$target" == local ]] && install_ingress_nginx
  # Feed files via stdin: Windows kubectl.exe cannot resolve MSYS /tmp paths.
  tk apply -f - <deploy/k8s/namespace.yaml
  if render_secrets "$secrets"; then
    apply_output="$(tk apply -f - <"$secrets")"
    echo "$apply_output"
    # The runtime reads its credentials once at startup. (CA bundle changes
    # roll it automatically through the hashed ConfigMap name.)
    if grep -Eq "^secret/application-agent-runtime-secrets (created|configured)" <<<"$apply_output"; then
      restart_runtime=true
    fi
  fi
  for d in application-agent-runtime-secrets lanadb-mcp-secrets; do
    tk -n "$namespace" get secret "$d" >/dev/null 2>&1 \
      || echo "WARNING: Secret $d is missing; see deploy/README.md" >&2
  done
  apply_output="$(tk apply -f - <"$manifests")"
  echo "$apply_output"
  # Pods read env-style ConfigMaps/Secrets only at startup, and a local reload
  # keeps the same <name>:<IMAGE_TAG> reference, so restart what changed.
  local -A restart=()
  [[ "${restart_runtime:-false}" == true ]] && restart[application-agent-runtime]=1
  for d in "${deployments[@]}"; do
    if grep -Eq "^configmap/$d-config (created|configured)" <<<"$apply_output"; then
      restart[$d]=1
    fi
    if [[ "$target" == local && "$do_load" == true && " ${images[*]} " == *" $d "* ]]; then
      restart[$d]=1
    fi
  done
  for d in "${deployments[@]}"; do
    [[ -n "${restart[$d]:-}" ]] && tk -n "$namespace" rollout restart "deploy/$d"
  done
  for d in "${deployments[@]}"; do
    tk -n "$namespace" rollout status "deploy/$d" --timeout=300s
  done
  tk -n "$namespace" get pods
  echo "OPO Monitoring UI: http://$(tk -n "$namespace" get ingress opo-monitoring -o 'jsonpath={.spec.rules[0].host}')/"
}

# ----------------------------------------------------------------- main ----

if [[ "$target" == local ]]; then setup_local; else setup_remote; fi

if [[ "$do_load" == true ]]; then
  check_local_images
  if [[ "$target" == local ]]; then load_local; else load_remote; fi
fi

[[ "$do_deploy" == true ]] && deploy

echo "Done."