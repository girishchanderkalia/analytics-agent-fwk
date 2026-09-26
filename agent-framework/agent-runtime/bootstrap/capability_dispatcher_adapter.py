"""Fixed capability-dispatch boundary for governed platform capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class CapabilityRegistryProtocol(Protocol):
    """Registry interface required by the fixed dispatcher."""

    def invoke(
        self,
        capability_id: str,
        state: Mapping[str, Any],
        permissions: frozenset[str],
        approved_capabilities: frozenset[str],
    ) -> Mapping[str, Any]:
        """Invoke one governed capability."""


class FixedCapabilityDispatcher:
    """Delegate workflow capability calls to the governed registry.

    Capability IDs, permissions, side-effect metadata, and approval policy stay
    in the declarative capability definitions and Capability Registry. This
    adapter only exposes the interface expected by Workflow Engine nodes.
    """

    def __init__(self, registry: CapabilityRegistryProtocol) -> None:
        self.registry = registry

    def invoke(
        self,
        capability_id: str,
        state: Mapping[str, Any],
        permissions: frozenset[str],
        approved_capabilities: frozenset[str],
    ) -> Mapping[str, Any]:
        """Invoke a capability through the fixed governed registry."""

        return self.registry.invoke(
            capability_id=capability_id,
            state=state,
            permissions=permissions,
            approved_capabilities=approved_capabilities,
        )


def create_capability_dispatcher(
    registry: CapabilityRegistryProtocol,
) -> FixedCapabilityDispatcher:
    """Create the framework-owned capability dispatcher."""

    return FixedCapabilityDispatcher(registry)
