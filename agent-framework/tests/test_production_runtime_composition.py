"""Tests for the fixed production runtime composition boundary."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))


from runtime_api.app import create_app  # noqa: E402
from runtime_api.production_composition import (  # noqa: E402
    create_production_runtime_service,
)
from runtime_api.production_policy import (  # noqa: E402
    DEFAULT_MAXIMUM_WORKFLOW_STEPS,
)
from runtime_api.settings import RuntimeSettings  # noqa: E402


def test_settings_only_expose_database_path() -> None:
    assert set(RuntimeSettings.model_fields) == {"database_path"}


def test_database_path_can_be_overridden(monkeypatch, tmp_path: Path) -> None:
    database_path = tmp_path / "runtime.db"
    monkeypatch.setenv(
        "AGENT_RUNTIME_DATABASE_PATH",
        str(database_path),
    )

    settings = RuntimeSettings()
    assert settings.resolved_database_path() == database_path.resolve()


def test_database_parent_is_created(tmp_path: Path) -> None:
    settings = RuntimeSettings(
        database_path=tmp_path / "nested" / "runtime.db"
    )
    path = settings.resolved_database_path()
    assert path.parent.exists()


def test_maximum_steps_is_fixed_framework_policy() -> None:
    assert DEFAULT_MAXIMUM_WORKFLOW_STEPS == 100


def test_readiness_is_ready_with_injected_service() -> None:
    response = TestClient(create_app(runtime_service=object())).get(
        "/ready"
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_is_not_ready_without_service() -> None:
    response = TestClient(create_app()).get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
