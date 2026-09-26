from __future__ import annotations

from typing import Protocol

from .models import AgentIdentity, AgentRegistration


class AgentRegistry(Protocol):
    def get(self, identity: AgentIdentity) -> AgentRegistration | None: ...
    def register(self, registration: AgentRegistration) -> None: ...
    def unregister(self, identity: AgentIdentity) -> None: ...


class ToolAvailability(Protocol):
    def contains(self, *, name: str, version: str, server: str) -> bool: ...
