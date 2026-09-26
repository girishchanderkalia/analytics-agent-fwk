"""Tests for the fixed governed capability dispatcher."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))


from bootstrap.capability_dispatcher_adapter import (  # noqa: E402
    FixedCapabilityDispatcher,
    create_capability_dispatcher,
)


class FakeCapabilityRegistry:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def invoke(
        self,
        capability_id: str,
        state: Mapping[str, Any],
        permissions: frozenset[str],
        approved_capabilities: frozenset[str],
    ) -> Mapping[str, Any]:
        self.calls.append(
            {
                "capability_id": capability_id,
                "state": dict(state),
                "permissions": permissions,
                "approved_capabilities": approved_capabilities,
            }
        )
        return {"trend_series": [{"id": "trend-1"}]}


def test_dispatcher_delegates_governance_inputs() -> None:
    registry = FakeCapabilityRegistry()
    dispatcher = FixedCapabilityDispatcher(registry)

    result = dispatcher.invoke(
        capability_id="data_query.read_trends",
        state={"question": "Show trends"},
        permissions=frozenset({"query:trends:read"}),
        approved_capabilities=frozenset(),
    )

    assert result == {"trend_series": [{"id": "trend-1"}]}
    assert registry.calls == [
        {
            "capability_id": "data_query.read_trends",
            "state": {"question": "Show trends"},
            "permissions": frozenset({"query:trends:read"}),
            "approved_capabilities": frozenset(),
        }
    ]


def test_factory_returns_fixed_dispatcher() -> None:
    registry = FakeCapabilityRegistry()
    dispatcher = create_capability_dispatcher(registry)
    assert isinstance(dispatcher, FixedCapabilityDispatcher)
    assert dispatcher.registry is registry


def test_dispatcher_does_not_swallow_registry_errors() -> None:
    class RejectingRegistry(FakeCapabilityRegistry):
        def invoke(self, **kwargs: Any) -> Mapping[str, Any]:
            raise PermissionError("Capability permission denied")

    dispatcher = create_capability_dispatcher(RejectingRegistry())

    try:
        dispatcher.invoke(
            capability_id="workspace.create",
            state={},
            permissions=frozenset(),
            approved_capabilities=frozenset(),
        )
    except PermissionError as exc:
        assert str(exc) == "Capability permission denied"
    else:
        raise AssertionError("PermissionError was not propagated")
