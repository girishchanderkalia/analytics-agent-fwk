"""Tests for validated application registration and production app wiring."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))

from host.application_registrations import (  # noqa: E402
    ApplicationRegistrationError,
    ApplicationRegistrations,
)
from host.runtime_context_factory import ExecutionSecurityContext  # noqa: E402


class FakeCapabilityRegistry:
    pass


def analyse_trends(state):
    return {"analysis": state.get("trend_series", [])}


def test_registrations_normalize_operations() -> None:
    registrations = ApplicationRegistrations(
        capability_registry=FakeCapabilityRegistry(),
        operations={" analyse_trends ": analyse_trends},
        security_context=ExecutionSecurityContext(
            permissions={"query:trends:read"},
            approved_capabilities={"workspace.create"},
        ),
    )

    assert list(registrations.operations) == ["analyse_trends"]
    assert registrations.security_context.permissions == frozenset(
        {"query:trends:read"}
    )


def test_missing_capability_registry_is_rejected() -> None:
    with pytest.raises(
        ApplicationRegistrationError,
        match="capability_registry",
    ):
        ApplicationRegistrations(
            capability_registry=None,
            operations={},
        )


def test_non_callable_operation_is_rejected() -> None:
    with pytest.raises(
        ApplicationRegistrationError,
        match="not callable",
    ):
        ApplicationRegistrations(
            capability_registry=FakeCapabilityRegistry(),
            operations={"analyse_trends": "invalid"},
        )
