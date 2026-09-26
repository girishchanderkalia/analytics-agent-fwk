"""Models shared by capability registration and invocation."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from typing import Any


CapabilityRequest = Mapping[str, Any]
CapabilityResult = dict[str, Any]
CapabilityHandler = Callable[[CapabilityRequest], CapabilityResult]


@dataclass(frozen=True)
class CapabilityContext:
    """Security and correlation context for one capability invocation."""

    permissions: frozenset[str] = field(
        default_factory=frozenset
    )
    approved: bool = False
    conversation_id: str | None = None
    correlation_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        permissions: Collection[str] | None = None,
        approved: bool = False,
        conversation_id: str | None = None,
        correlation_id: str | None = None,
    ) -> "CapabilityContext":
        """Create a normalized capability context."""

        return cls(
            permissions=frozenset(permissions or ()),
            approved=approved,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
        )


@dataclass(frozen=True)
class CapabilityDefinition:
    """Metadata and implementation for one external capability."""

    capability_id: str
    operation: str
    handler: CapabilityHandler
    description: str = ""
    owner: str = ""
    version: str = "1.0"
    required_permissions: frozenset[str] = field(
        default_factory=frozenset
    )
    approval_required: bool = False
    side_effect: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return public metadata without exposing the handler."""

        return {
            "id": self.capability_id,
            "operation": self.operation,
            "description": self.description,
            "owner": self.owner,
            "version": self.version,
            "required_permissions": sorted(
                self.required_permissions
            ),
            "approval_required": self.approval_required,
            "side_effect": self.side_effect,
        }


@dataclass(frozen=True)
class CapabilityInvocation:
    """Input for one capability invocation."""

    capability_id: str
    request: CapabilityRequest
    context: CapabilityContext = field(
        default_factory=CapabilityContext
    )