# Slice 13K end-to-end integration tests

This package validates the deployed boundaries built in Slices 13A through 13J.
It is intentionally black-box and calls public HTTP endpoints only. The two
front-end paths are covered end to end through the OPO Monitoring BFF: the
deterministic path to Analytics Foundation (`-m deterministic`) and the chat
path to the Agent Runtime (`-m agent`).

The default suite runs health, discovery, deterministic BFF, chat contract and
error-mapping, and architecture checks. Model-backed chat tests are enabled with
`RUN_AGENT_E2E=true` so that normal local validation does not require model
credentials.

## Run locally

From anywhere in the repository, in Git Bash, run:

```bash
./scripts/run-e2e-tests.sh
```

This is the entry point to use after a fresh clone. It verifies the toolchain,
then delegates to `scripts/run-integration-tests.sh`. Pass `--with-agent` to
include the model-backed chat tests, `--help` for the full usage, and any other
arguments straight through to pytest, for example
`scripts/run-e2e-tests.sh -m deterministic`.

The runner finds Python 3.13 or newer (including installed conda environments),
creates `.run/slice13k/venv`, and installs the runtime, service, and test
dependencies from their manifests. Later runs reuse the environment and
reinstall when manifests change. No separate Python package installation is
needed. Python 3.13+, Java, and Maven must be installed; set `PYTHON_BIN` to a
compatible base interpreter if discovery fails and `JAVA_HOME` if Java is not
on `PATH`.

The runner starts the services, waits for readiness, runs pytest, then stops
the services even when tests fail. It rejects ports or service PID files already
in use.

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

The default run skips the model-backed chat tests. Run them with
`RUN_AGENT_E2E=true` only when the runtime has a working model gateway
configuration. Stop the services with Ctrl+C in the launcher terminal or
run `scripts/stop-services.sh` from the repository root.

## Browser (UI) tests

`tests/test_ui_agent_workflow.py` drives the real OPO Monitoring front end with
Playwright. The UI is served on the BFF origin, so the browser exercises the
same `/api/trends/**` and `/api/investigations/**` routes a user would.

```bash
./scripts/run-ui-tests.sh
```

That wrapper is `scripts/run-e2e-tests.sh --ui-only`; the browser tests are part
of the default e2e run and need no separate setup. The runner installs the
Chromium browser binary the first time dependencies are provisioned.

Without `RUN_AGENT_E2E=true` the UI run covers page load, deterministic trend
rendering, thread-reopen error handling, and panel behaviour. With
`RUN_AGENT_E2E=true` it also walks the full human-in-the-loop agent workflow
from the browser: send a message, answer each gate, assert a terminal outcome.

```bash
RUN_AGENT_E2E=true ./scripts/run-ui-tests.sh
```

Add `--headed --slowmo 300` to watch the browser, or `--video retain-on-failure`
to capture failures.

