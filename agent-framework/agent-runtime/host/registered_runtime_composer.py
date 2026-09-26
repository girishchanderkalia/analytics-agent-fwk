"""Compose per-agent runtimes from validated application registrations."""

from __future__ import annotations

from typing import Any

from .application_registrations import ApplicationRegistrations
from .fixed_runtime_composer import FixedRuntimeComposer, ComposedAgentExecution


class RegisteredRuntimeComposer:
    """Single application-level entry into fixed per-agent composition."""

    def __init__(
        self,
        registrations: ApplicationRegistrations,
        maximum_steps: int = 100,
    ) -> None:
        self.registrations = registrations
        self.composer = FixedRuntimeComposer(
            capability_registry=registrations.capability_registry,
            operations=registrations.operations,
            security_context=registrations.security_context,
            maximum_steps=maximum_steps,
        )

    def compose(self, bundle: Any) -> ComposedAgentExecution:
        """Compose one resolved agent bundle."""

        return self.composer.compose(bundle)
