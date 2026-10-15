# Kubernetes deployment

This deployment runs the OPO Monitoring UI/BFF, the Agent Runtime, the
Analytics Foundation API and MCP provider, and the LanaDB MCP adapter in one
Kubernetes namespace (`ai-agent-fwk`). Only the UI is exposed through an
Ingress; the remaining services use internal `ClusterIP` Services.

The Analytics Foundation API in this repository is a file-backed mock/reference
service. The LanaDB MCP adapter connects to an existing PostgreSQL-compatible
LanaDB endpoint, and the Agent Runtime connects to an existing model gateway.
Those external systems, their credentials, DNS, and network routes must be
provisioned for the cluster separately; private CA trust for the model gateway
is supplied as described in [Model gateway CA bundle](#model-gateway-ca-bundle).

## Overview

Deployment uses two Git Bash scripts, run from the repository root, and one
config file that describes the target cluster:

| Script | What it does |
| --- | --- |
| [`build/build-containers.sh`](../build/build-containers.sh) | Builds the five images in the workstation's local Docker as `<name>:<IMAGE_TAG>`. Nothing is pushed. |
| [`build/deploy.sh`](../build/deploy.sh) | Loads those images into the target cluster, creates/updates the Secrets, applies [`k8s/`](./k8s) with matching image references, and waits for all rollouts. |

Both scripts take `--config FILE` (default `build/local.conf`); everything
about the target comes from that file:

| Config | `TARGET` | Where images go |
| --- | --- | --- |
| [`build/local.conf`](../build/local.conf) | `local` | Imported straight into the local cluster node's containerd (Docker Desktop / kind). No registry. |
| `build/remote.conf` (from [`build/remote.conf.example`](../build/remote.conf.example)) | `remote` | Copied to the cluster's management node over SSH, then `podman load/tag/push` to the cluster registry. |

The images are `application-agent-runtime`, `analytics-foundation-api`,
`analytics-foundation-mcp`, `lanadb-mcp`, and `opo-monitoring`. The OPO image
builds and tests the Java BFF and packages the static UI; the Foundation API
image includes the checked-in mock datasets. Both scripts accept
`--images a,b` to work on a subset; run them with `--help` for all options.

`deploy.sh` options:

- (none): load the images and deploy.
- `--images LIST`: load/update only these images; other Deployments keep the
  image they currently run.
- `--skip-load`: only deploy (config, Secrets, CA bundle, manifest changes).
- `--load-only`: only load images, do not deploy.

The `registry.example.com/<name>:latest` image names in
[`k8s/kustomization.yaml`](./k8s/kustomization.yaml) are placeholders that
`deploy.sh` (and the [`overlays/local`](./overlays/local/kustomization.yaml)
overlay) replace with the real image references; keep them unchanged.

## Before the first deployment

These steps apply to both local and remote clusters.

### Configure cluster-specific values

- [`k8s/configmap.yaml`](./k8s/configmap.yaml): set
  `MODEL_GATEWAY_ENDPOINT` and `MODEL_GATEWAY_MODEL` to the approved model
  gateway endpoint and model name. For an Azure provider, set
  `MODEL_GATEWAY_PROVIDER=azure`, `MODEL_GATEWAY_DEPLOYMENT`, and
  `MODEL_GATEWAY_API_VERSION` (Azure always uses Chat Completions). The
  `openai` provider uses the OpenAI Responses API by default, which reasoning
  models (for example gpt-6) need for tool calls; set
  `MODEL_GATEWAY_OPENAI_API=chat` for endpoints that only implement
  `/chat/completions`. The agent package directories and internal MCP
  URLs are already wired to the paths and Services in this repository.
- [`k8s/lanadb-mcp.yaml`](./k8s/lanadb-mcp.yaml): adjust schema, connection
  pool, and row limits if required.
- [`k8s/ingress.yaml`](./k8s/ingress.yaml): set the ingress class and default
  DNS host for the controller installed in the cluster (`INGRESS_HOST` in the
  deployment config overrides the host). Configure TLS through the
  cluster's certificate workflow before exposing this service publicly.

The runtime image registers both `agents/opo-analysis-agent` and
`agents/opo-generic-agent` for application ID `opo-monitoring`, matching the
agents requested by the UI.

### Create credentials

`deploy.sh` reads Secret values from a single gitignored env file: the
repo-root `.env` (copy [`.env.example`](../.env.example) to get started), or
whatever `SECRETS_ENV_FILE` in your deployment config points at. The same
file also configures local runs (`scripts/start-services.sh`), so it must
hold the keys appropriate for the cluster you are about to deploy to:

```text
MODEL_GATEWAY_API_KEY=<model gateway API key>

LANADB_JDBC_URL=jdbc:postgresql://<database-host>:<port>/<database>
LANADB_USERNAME=<database username>
LANADB_PASSWORD=<database password>
```

When the same `.env` is also used for local development against a different
database, keep both sets of `LANADB_*`/`MODEL_GATEWAY_*` values in the file
and comment out the one that doesn't apply before running `deploy.sh` (the
toggle-by-comment pattern already used for `MODEL_GATEWAY_PROVIDER`). Only
the last uncommented `KEY=` line for each key is used. Deploying to a remote
cluster with a `LANADB_JDBC_URL` pointing at `localhost`/`127.0.0.1` prints a
warning, since that is almost always a local-only database.

`deploy.sh` creates or updates the Secrets `application-agent-runtime-secrets`
and `lanadb-mcp-secrets` from this file on every deployment (for a remote
cluster, through `kubectl` on the management node) and restarts the runtime
when its Secret changed. Values are never printed. If the file is absent,
existing Secrets are left unchanged and a warning is shown for missing ones.

### Model gateway CA bundle

When the model gateway endpoint uses a corporate/private CA (provider
`azure`), the runtime trusts the PEM file at `AGENT_RUNTIME_CA_BUNDLE_PATH`
(`/etc/agent-runtime/ca/ca-bundle.pem` in
[`k8s/configmap.yaml`](./k8s/configmap.yaml)). The bundle is checked in as
[`k8s/ca-bundle.pem`](./k8s/ca-bundle.pem) (public certificates only, no
keys), and the `configMapGenerator` in
[`k8s/kustomization.yaml`](./k8s/kustomization.yaml) turns it into the
ConfigMap `application-agent-runtime-ca-bundle-<hash>` that the runtime
Deployment mounts.

The bundle replaces the default trust store (it is exported as
`SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`), so it must be a combined bundle that
contains the corporate root/intermediate CAs and the public CAs the runtime
needs. To update it, replace `deploy/k8s/ca-bundle.pem` (keep the file name)
and run `./build/deploy.sh --skip-load` (add `--config build/remote.conf` for
the remote cluster). The ConfigMap name hash changes with the content, so the
runtime rolls out automatically with the new bundle.

## Local K8s deployment

For Docker Desktop's Kubernetes, kind, or any containerd-based cluster that
allows privileged pods. Prerequisites: Docker, `kubectl`, and Git Bash.

[`build/local.conf`](../build/local.conf) is checked in:

| Key | Default | Meaning |
| --- | --- | --- |
| `TARGET` | `local` | Local cluster. |
| `IMAGE_TAG` | `local` | Images are built and deployed as `<name>:local`. |
| `KUBE_CONTEXT` | (empty) | kubectl context; empty uses the current context, e.g. `docker-desktop`. |
| `INGRESS_NGINX_VERSION` | `1.15.1` | ingress-nginx controller version installed by `deploy.sh`; empty skips the install (use an existing controller). |
| `INGRESS_HOST` | `localhost` | Host of the OPO Monitoring Ingress; empty keeps the host from `k8s/ingress.yaml`. |

Build and deploy everything, then open the UI at <http://localhost/>:

```bash
./build/build-containers.sh
./build/deploy.sh
```

`deploy.sh` imports each image directly into every node's containerd (through
`kind load` for `kind-*` contexts, otherwise through a short-lived privileged
helper pod running `ctr import`), so no registry is needed.

Before applying the application, `deploy.sh` installs the ingress-nginx
controller (namespace `ingress-nginx`) from the official release manifest for
`INGRESS_NGINX_VERSION`. It is skipped when that version is already installed
and replaced when the version changes. Docker Desktop exposes the controller's
`LoadBalancer` Service on `localhost:80/443`. For kind (`kind-*` contexts) the
kind provider manifest is used; the cluster must be created with
`extraPortMappings` for ports 80/443 and a node labelled `ingress-ready=true`
(see the kind ingress guide). Ports 80 and 443 must be free on the workstation.

Examples:

```bash
# Rebuild and redeploy only the runtime and the UI; other services are untouched
./build/build-containers.sh --images application-agent-runtime,opo-monitoring
./build/deploy.sh --images application-agent-runtime,opo-monitoring

# Redeploy config, Secret, or CA bundle changes without loading images
./build/deploy.sh --skip-load

# Only load the images, then apply the local overlay yourself
./build/deploy.sh --load-only
kubectl apply -k deploy/overlays/local

# Use a different local cluster or tag: copy the config and edit it
cp build/local.conf build/kind.conf     # e.g. KUBE_CONTEXT=kind-dev
./build/build-containers.sh --config build/kind.conf
./build/deploy.sh --config build/kind.conf
```

If `INGRESS_NGINX_VERSION` is empty and the cluster has no Ingress controller,
reach the UI with
`kubectl -n ai-agent-fwk port-forward svc/opo-monitoring 8080:80` and open
`http://localhost:8080`.

## Remote K8s deployment

The remote cluster is driven from its management node over SSH using the keys
or certificates already installed for your user; no credentials are stored in
the config. The management node needs `podman`, `gzip`, and `kubectl` with
access to the cluster, and the cluster nodes must be able to pull from its
registry. The workstation needs Docker, `kubectl` (only to render the
manifests), `ssh`, and Git Bash.

Create the config once (`build/*.conf` other than `local.conf` is gitignored):

```bash
cp build/remote.conf.example build/remote.conf
```

| Key | Example | Meaning |
| --- | --- | --- |
| `TARGET` | `remote` | Remote cluster via its management node. |
| `IMAGE_TAG` | `local` | Tag of the images built locally (`<name>:<IMAGE_TAG>`). |
| `REMOTE_HOST` | `mgmt-node.cluster.local` | Management node. |
| `REMOTE_USER` / `REMOTE_PORT` | `deploy` / `22` | SSH user (empty = SSH default) and port. |
| `SSH_IDENTITY_FILE` / `SSH_OPTIONS` | (empty) | Optional private key and extra `ssh` arguments. |
| `REMOTE_WORK_DIR` | `/tmp/analytics-agent-fwk-images` | Where image tar files are staged on the management node. |
| `REMOTE_REGISTRY` / `REMOTE_REGISTRY_PATH` | `repo.cluster.local:5443` / (empty) | Cluster registry and optional path. |
| `REMOTE_IMAGE_TAG` | (empty) | Tag pushed to the registry; empty = new timestamp tag (`YYYYmmddHHMMSS`) on every load. |
| `PODMAN_CMD` / `PODMAN_PUSH_OPTIONS` | `podman` / (empty) | podman command and extra push flags, e.g. `--tls-verify=false`. |
| `REMOTE_KUBECTL` | `kubectl` | kubectl command on the management node. |
| `INGRESS_HOST` | (empty) | DNS host of the OPO Monitoring Ingress; empty keeps the host from `k8s/ingress.yaml`. |

The remote cluster must already run an `nginx`-class Ingress controller;
`deploy.sh` does not install one there.

Build and deploy everything:

```bash
./build/build-containers.sh --config build/remote.conf
./build/deploy.sh --config build/remote.conf
```

For each image, `deploy.sh` streams `docker save` (gzip-compressed) to
`REMOTE_WORK_DIR` on the management node and runs there:

```bash
podman load < <name>-<IMAGE_TAG>.tar
podman tag localhost/<name>:<IMAGE_TAG> <REMOTE_REGISTRY>[/<REMOTE_REGISTRY_PATH>]/<name>:<tag>
podman push [PODMAN_PUSH_OPTIONS] <REMOTE_REGISTRY>[/<REMOTE_REGISTRY_PATH>]/<name>:<tag>
```

The tar file is removed after the push. It then applies the rendered
manifests and Secrets with `kubectl` on the management node and waits for the
rollouts. Every load uses a new tag by default because the manifests use
`imagePullPolicy: IfNotPresent`: re-pushing an existing tag would not be
picked up by nodes that already cached it. Set `REMOTE_IMAGE_TAG` only for a
fixed release tag (e.g. `1.2.0`) that is pushed once.

Examples:

```bash
# Rebuild and redeploy only the runtime; other Deployments keep their image
./build/build-containers.sh --config build/remote.conf --images application-agent-runtime
./build/deploy.sh --config build/remote.conf --images application-agent-runtime

# Redeploy config, Secret, or CA bundle changes with the images already running
./build/deploy.sh --config build/remote.conf --skip-load

# Only push the images to the cluster registry, deploy later
./build/deploy.sh --config build/remote.conf --load-only

# Release with a fixed tag: set REMOTE_IMAGE_TAG=1.2.0 in a copy of the config
cp build/remote.conf build/remote-release.conf
./build/deploy.sh --config build/remote-release.conf
```

## Runtime notes

The cluster must have an `nginx`-class Ingress controller (installed by
`deploy.sh` for local clusters), a default (or selected) dynamic
storage provisioner for the runtime PVC, and network access from workloads to
the model gateway and LanaDB.

The runtime uses one replica and a persistent volume for SQLite conversation
metadata. LangGraph checkpoints use the in-memory backend because the runtime
invokes graphs asynchronously and the framework's `sqlite`/`postgres`
checkpointer factories currently create synchronous savers; paused
conversations therefore cannot be resumed after a runtime pod restart. Keep a
single runtime replica while using SQLite and `ReadWriteOnce`; back up the PVC
as part of the cluster's normal storage policy. Scaling the runtime
horizontally requires a shared checkpoint/metadata backend and a corresponding
application change.

Once the Ingress controller has assigned an address and DNS points to it, open
the configured hostname. The internal service endpoints are:

- `http://application-agent-runtime:8000`
- `http://analytics-foundation-api:8200`
- `http://analytics-foundation-mcp:8300/mcp`
- `http://lanadb-mcp:8400/mcp`

Check readiness and logs when a deployment does not become available (on the
management node for the remote cluster):

```bash
kubectl -n ai-agent-fwk get deployments,pods,services,ingress,pvc
kubectl -n ai-agent-fwk describe pod <pod-name>
kubectl -n ai-agent-fwk logs deployment/<deployment-name>
```

## Validate manifests

```bash
kubectl kustomize deploy/k8s >/dev/null
kubectl apply --dry-run=client -k deploy/overlays/local
```