# Slice 13K end-to-end integration tests

This package validates the deployed boundaries built in Slices 13A through 13J.
It is intentionally black-box and calls public HTTP endpoints only.

The default suite runs health, discovery, deterministic BFF, and architecture
checks. Model-backed chat tests are enabled with `RUN_AGENT_E2E=true` so that
normal local validation does not require model credentials.

## Run locally

From the repository root in Git Bash, run:

```bash
./scripts/run-integration-tests.sh
```

The runner finds Python 3.13 or newer (including installed conda environments),
creates `.run/slice13k/venv`, and installs the runtime, service, and test
dependencies from their manifests. Later runs reuse the environment and
reinstall when manifests change. No separate Python package installation is
needed. Python 3.13+, Java, and Maven must be installed; set `PYTHON_BIN` to a
compatible base interpreter if discovery fails and `JAVA_HOME` if Java is not
on `PATH`.

The runner starts the services, waits for readiness, runs pytest, then stops
the services even when tests fail. It rejects ports or service PID files already
in use. Pass pytest arguments to run a subset, for example
`scripts/run-integration-tests.sh -m smoke`.

For manual debugging, start the services in one terminal:

```bash
export PYTHON_BIN="$PWD/.run/slice13k/venv/Scripts/python.exe"
scripts/start-services.sh
```

The manual command uses the environment created by an earlier runner invocation.
Leave that terminal running. In another terminal:

```bash
export PYTHON_BIN="$PWD/.run/slice13k/venv/Scripts/python.exe"
cd agent-framework/integration-tests
"$PYTHON_BIN" -m pytest -q
```

The default run skips two model-backed chat tests. Run them with
`RUN_AGENT_E2E=true` only when the runtime has a working model gateway
configuration. Stop the services with Ctrl+C in the launcher terminal or
run `scripts/stop-services.sh` from the repository root.
