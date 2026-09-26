"""Validated application registrations consumed by production bootstrap."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from bootstrap.capability_dispatcher_adapter import CapabilityRegistryProtocol
from bootstrap.operation_registry_bootstrap import OperationHandler
from .runtime_context_factory import ExecutionSecurityContext


class ApplicationRegistrationError(ValueError):
    """Raised when fixed application registrations are incomplete."""


@dataclass(frozen=True)
class ApplicationRegistrations:
    """Concrete registrations owned by one application runtime deployment."""

    capability_registry: CapabilityRegistryProtocol
    operations: Mapping[str, OperationHandler]
    security_context: ExecutionSecurityContext = field(
        default_factory=ExecutionSecurityContext
    )

    def __post_init__(self) -> None:
        if self.capability_registry is None:
            raise ApplicationRegistrationError(
                "capability_registry must not be None"
            )

        if not isinstance(self.operations, Mapping):
            raise ApplicationRegistrationError(
                "operations must be a mapping"
            )

        normalized: dict[str, OperationHandler] = {}

        for name, handler in self.operations.items():
            if not isinstance(name, str) or not name.strip():
                raise ApplicationRegistrationError(
                    "operation names must be non-empty strings"
                )
            if not callable(handler):
                raise ApplicationRegistrationError(
                    f"operation handler is not callable: {name!r}"
                )
            normalized[name.strip()] = handler

        object.__setattr__(self, "operations", normalized)
