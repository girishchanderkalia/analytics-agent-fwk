from __future__ import annotations

import sys
from pathlib import Path
from shutil import copytree

import pytest


TESTS_ROOT = Path(__file__).resolve().parent
AGENT_FRAMEWORK_ROOT = TESTS_ROOT.parent
AGENT_RUNTIME_ROOT = AGENT_FRAMEWORK_ROOT / "agent-runtime"
TEST_AGENT_ROOT = TESTS_ROOT / "fixtures" / "test-agent"


if not AGENT_RUNTIME_ROOT.is_dir():
    raise RuntimeError(
        "Agent Runtime source directory does not exist: "
        f"{AGENT_RUNTIME_ROOT}"
    )

agent_runtime_path = str(AGENT_RUNTIME_ROOT)

if agent_runtime_path not in sys.path:
    sys.path.insert(0, agent_runtime_path)


@pytest.fixture
def test_agent_root() -> Path:
    """Return the generic agent package used by framework tests."""
    return TEST_AGENT_ROOT


@pytest.fixture
def copied_test_agent_root(
    tmp_path: Path,
    test_agent_root: Path,
) -> Path:
    """Copy the generic agent package for mutation tests."""
    copied_root = tmp_path / "test-agent"
    copytree(test_agent_root, copied_root)
    return copied_root
