from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from .errors import RegistrationValidationError
from .loader import AgentPackageLoader
from .models import AgentIdentity, AgentRegistration
from .protocols import AgentRegistry, ToolAvailability


class RegistrationBootstrap:
    """Atomically validate and register declarative agent packages."""

    def __init__(
        self,
        registry: AgentRegistry,
        *,
        loader: AgentPackageLoader | None = None,
        tool_availability: ToolAvailability | None = None,
        allow_planned_tools: bool = True,
    ) -> None:
        self._registry = registry
        self._loader = loader or AgentPackageLoader()
        self._tools = tool_availability
        self._allow_planned = allow_planned_tools

    def register_all(
        self,
        manifests: Iterable[str | Path],
    ) -> tuple[AgentRegistration, ...]:
        loaded = tuple(self._loader.load(path) for path in manifests)
        self._validate_unique(loaded)
        for registration in loaded:
            self._validate_tools(registration)
        changed: list[AgentIdentity] = []
        try:
            for registration in loaded:
                current = self._registry.get(registration.identity)
                if current is not None and current.fingerprint == registration.fingerprint:
                    continue
                self._registry.register(registration)
                changed.append(registration.identity)
        except Exception:
            for identity in reversed(changed):
                self._registry.unregister(identity)
            raise
        return loaded

    def _validate_unique(self, registrations):
        identities = [item.identity for item in registrations]
        if len(identities) != len(set(identities)):
            raise RegistrationValidationError("Duplicate agent identity in bootstrap input")

    def _validate_tools(self, registration):
        if self._tools is None:
            return
        missing = []
        for tool in registration.tools:
            if self._allow_planned and tool.availability:
                continue
            if not self._tools.contains(
                name=tool.name,
                version=tool.version,
                server=tool.server,
            ):
                missing.append(f"{tool.server}:{tool.name}:{tool.version}")
        if missing:
            raise RegistrationValidationError(
                "Unavailable tools: " + ", ".join(sorted(missing))
            )


def bootstrap_from_environment(
    registry: AgentRegistry,
    *,
    tool_availability: ToolAvailability | None = None,
    variable: str = "AGENT_PACKAGE_MANIFESTS",
) -> tuple[AgentRegistration, ...]:
    """Register semicolon-separated package manifests from an environment variable."""
    raw = os.getenv(variable, "").strip()
    if not raw:
        return ()
    manifests = [Path(value.strip()) for value in raw.split(";") if value.strip()]
    return RegistrationBootstrap(
        registry,
        tool_availability=tool_availability,
    ).register_all(manifests)
