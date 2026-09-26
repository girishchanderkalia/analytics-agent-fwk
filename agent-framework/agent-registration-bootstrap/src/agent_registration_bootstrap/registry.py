from __future__ import annotations

from threading import RLock

from .errors import DuplicateAgentRegistrationError
from .models import AgentIdentity, AgentRegistration


class InMemoryAgentRegistry:
    """Small reference registry used by tests and local composition."""

    def __init__(self) -> None:
        self._items: dict[AgentIdentity, AgentRegistration] = {}
        self._lock = RLock()

    def get(self, identity: AgentIdentity) -> AgentRegistration | None:
        with self._lock:
            return self._items.get(identity)

    def register(self, registration: AgentRegistration) -> None:
        with self._lock:
            current = self._items.get(registration.identity)
            if current is not None and current.fingerprint != registration.fingerprint:
                raise DuplicateAgentRegistrationError(
                    f"Conflicting registration for {registration.identity}"
                )
            self._items[registration.identity] = registration

    def unregister(self, identity: AgentIdentity) -> None:
        with self._lock:
            self._items.pop(identity, None)

    def snapshot(self) -> tuple[AgentRegistration, ...]:
        with self._lock:
            return tuple(self._items[key] for key in sorted(self._items))
