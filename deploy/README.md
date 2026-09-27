# Agent Runtime deployment slice

This slice packages the tested Agent Runtime as a non-root container and adds
Kubernetes manifests for the `agents` namespace.

## Prerequisites

- `requirements.txt` must include the runtime dependencies already used by the
  passing test suite.
- `runtime_api.langgraph_main:app` serves `GET /health`, `GET /ready`,
  `GET /v1/applications/{application_id}/agents`, `POST /v1/chat`,
  `POST /v1/conversations/{conversation_id}/resume`, and
  `GET /v1/conversations/{conversation_id}`.
- The image registers `agents/opo-monitoring` for application `opo-monitoring`;
  override `AGENT_APPLICATION_ID` and `AGENT_MARKDOWN_PACKAGES` for other packages.
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
