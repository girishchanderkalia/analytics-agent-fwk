# Analytics Agent Framework

## Running Low-Level Tests

The repository's isolated Python component tests and the OPO Java BFF tests can
be run with one script. The script does not require Conda and does not start
services or run integration tests.

### Prerequisites

- Python 3.13 or newer. Install a standard Python distribution if needed and
  make its executable available on `PATH`, or provide its executable path with
  `BASE_PYTHON` as shown below.
- Java Development Kit 21 or newer and Maven, both available on `PATH`. Maven
  downloads the BFF's Java dependencies when the script runs.
- Git Bash on Windows, or Bash on Linux/macOS.

### Run

From the repository root, when `python` resolves to Python 3.13 or newer:

```bash
bash scripts/run-low-level-tests.sh
```

If the default `python` is older or you have multiple Python installations,
point `BASE_PYTHON` to the Python 3.13+ executable. This creates the test
virtual environment from that interpreter without changing global Python
environment variables.

```bash
# Windows Git Bash example; replace this with the Python executable path on your machine.
BASE_PYTHON=/c/path/to/python3.13.exe bash scripts/run-low-level-tests.sh

# Linux/macOS example
BASE_PYTHON=/usr/bin/python3.13 bash scripts/run-low-level-tests.sh
```

The script creates or reuses `.venv-low-level-tests` (or a compatible existing
`.venv`), installs Python dependencies from explicit requirements files, then
runs the OPO logic, agent-package, response-compatibility, capability-service,
Analytics Foundation API/client/MCP, agent-framework, registration-bootstrap,
and Java BFF tests. Python source packages are loaded from their repository
paths; the script does not install them in editable mode.

To use an already-created Python environment directly instead of creating a
virtual environment, set `PYTHON` to its Python executable. The script installs
the required dependencies into that environment:

```bash
PYTHON=/path/to/python3.13 bash scripts/run-low-level-tests.sh
```

This runner covers local unit/component tests only. The deployed black-box
integration tests are separate and require the relevant services to be running.
