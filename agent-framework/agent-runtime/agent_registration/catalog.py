"""Thread-safe in-memory catalog for registered prebuilt agents."""

from __future__ import annotations

from threading import RLock

from .errors import AgentAlreadyRegisteredError
from .models import AgentRegistrationKey, AgentRegistrationRecord


class InMemoryAgentRegistrationCatalog:
    """Store validated registrations without repository auto-discovery."""

    def __init__(self) -> None:
        self._records: dict[
            AgentRegistrationKey,
            AgentRegistrationRecord,
        ] = {}
        self._lock = RLock()

    def contains(self, key: AgentRegistrationKey) -> bool:
        with self._lock:
            return key in self._records

    def get(self, key: AgentRegistrationKey) -> AgentRegistrationRecord:
        with self._lock:
            return self._records[key]

    def list_for_application(
        self,
        application_id: str,
    ) -> tuple[AgentRegistrationRecord, ...]:
        with self._lock:
            return tuple(
                record
                for key, record in sorted(self._records.items())
                if key.application_id == application_id
            )

    def register_atomic(
        self,
        records: tuple[AgentRegistrationRecord, ...],
    ) -> None:
        """Add all records or none if any key already exists."""

        with self._lock:
            duplicates = [
                record.key
                for record in records
                if record.key in self._records
            ]

            if duplicates:
                duplicate = duplicates[0]
                raise AgentAlreadyRegisteredError(
                    "Agent registration already exists: "
                    f"{duplicate.application_id}/"
                    f"{duplicate.agent_id}/{duplicate.version}"
                )

            staged = dict(self._records)
            for record in records:
                staged[record.key] = record

            self._records = staged

    def snapshot(self) -> tuple[AgentRegistrationRecord, ...]:
        with self._lock:
            return tuple(
                self._records[key]
                for key in sorted(self._records)
            )
