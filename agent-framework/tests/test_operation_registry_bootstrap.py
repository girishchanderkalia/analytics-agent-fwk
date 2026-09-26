"""Tests for fixed deterministic-operation wiring."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))


from bootstrap.operation_registry_bootstrap import (  # noqa: E402
    OperationRegistryBootstrapError,
    create_operation_registry,
    validate_workflow_operations,
)


class FakeRegistry:
    def __init__(self) -> None:
        self.handlers: dict[str, Any] = {}

    def register(self, name: str, handler: Any) -> None:
        if name in self.handlers:
            raise ValueError(f"Duplicate operation: {name}")
        self.handlers[name] = handler

    def invoke(self, name: str, state: dict[str, Any]) -> Any:
        return self.handlers[name](state)


def analyse_trends(state: dict[str, Any]) -> dict[str, Any]:
    return {"analysis": state.get("trend_series", [])}


def test_registry_registers_application_operation() -> None:
    registry = FakeRegistry()
    result = create_operation_registry(
        {"analyse_trends": analyse_trends},
        registry=registry,
    )

    assert result is registry
    assert result.invoke(
        "analyse_trends",
        {"trend_series": [{"id": "trend-1"}]},
    ) == {"analysis": [{"id": "trend-1"}]}


def test_non_callable_handler_is_rejected() -> None:
    with pytest.raises(
        OperationRegistryBootstrapError,
        match="not callable",
    ):
        create_operation_registry(
            {"analyse_trends": "not-a-function"},
            registry=FakeRegistry(),
        )


def test_duplicate_registration_is_rejected() -> None:
    registry = FakeRegistry()
    registry.register("analyse_trends", analyse_trends)

    with pytest.raises(
        OperationRegistryBootstrapError,
        match="Cannot register",
    ):
        create_operation_registry(
            {"analyse_trends": analyse_trends},
            registry=registry,
        )


def test_missing_declared_operation_is_rejected() -> None:
    bundle = SimpleNamespace(
        workflow=SimpleNamespace(
            metadata={
                "nodes": [
                    {
                        "id": "analyse",
                        "type": "operation",
                        "operation": "analyse_trends",
                    }
                ]
            }
        )
    )

    with pytest.raises(
        OperationRegistryBootstrapError,
        match="analyse_trends",
    ):
        validate_workflow_operations(bundle, {})


def test_declared_operation_validation_passes() -> None:
    bundle = SimpleNamespace(
        workflow=SimpleNamespace(
            metadata={
                "nodes": [
                    {
                        "id": "analyse",
                        "type": "operation",
                        "operation": "analyse_trends",
                    },
                    {
                        "id": "summarize",
                        "type": "model",
                    },
                ]
            }
        )
    )

    validate_workflow_operations(
        bundle,
        {"analyse_trends": analyse_trends},
    )
