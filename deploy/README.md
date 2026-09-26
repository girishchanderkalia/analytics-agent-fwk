# Agent Runtime deployment slice

This slice packages the tested Agent Runtime as a non-root container and adds
Kubernetes manifests for the `agents` namespace.

## Prerequisites

- `requirements.txt` must include the runtime dependencies already used by the
  passing test suite.
- `api.app:app` must expose `GET /health`, `POST /chat`, and `POST /resume`.
- The CA bundle ConfigMap must already exist as
  `application-agent-runtime-ca-bundle` with key `combined-ca-bundle.pem`.
- Replace all `REPLACE_WITH_...` values before applying manifests.
- Do not commit a populated Secret manifest.

## Build

```bash
chmod +x deploy/scripts/build-runtime-image.sh
deploy/scripts/build-runtime-image.sh
```

## Validate manifests

```bash
kubectl apply --dry-run=client -k deploy/k8s
```

## Apply

Create the secret separately, then apply the non-secret resources:

```bash
kubectl apply -f deploy/k8s/secret-template.yaml
kubectl apply -k deploy/k8s
```

The Secret template contains placeholders only. Prefer generating the real
Secret YAML on a trusted host and transferring it to the cluster host.
