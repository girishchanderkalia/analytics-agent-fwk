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

    def resolve(
        self,
        application_id: str,
        agent_id: str,
        version: str | None = None,
    ) -> AgentRegistrationRecord:
        """Resolve one registered agent owned by an application.

        An application may register several agents and several versions, so
        both identifiers are required; the latest version is used only when no
        version is requested.
        """

        key = (application_id, agent_id)
        with self._lock:
            matches = [
                record
                for record_key, record in sorted(self._records.items())
                if (record_key.application_id, record_key.agent_id) == key
                and (version is None or record_key.version == version)
            ]

        if not matches:
            raise KeyError(f"{application_id}/{agent_id}/{version or 'latest'}")
        return matches[-1]

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
