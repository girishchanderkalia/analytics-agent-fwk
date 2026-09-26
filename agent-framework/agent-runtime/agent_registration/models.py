"""Immutable models for bulk application-agent registration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

from .errors import AgentRegistrationValidationError


class RegistrationStatus(StrEnum):
    """Public result of one bulk registration operation."""

    REGISTERED = "registered"
    REJECTED = "rejected"


@dataclass(frozen=True, order=True)
class AgentRegistrationKey:
    """Unique identity of one application-owned agent version."""

    application_id: str
    agent_id: str
    version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "application_id",
            _required_text(self.application_id, "application_id"),
        )
        object.__setattr__(
            self,
            "agent_id",
            _required_text(self.agent_id, "agent_id"),
        )
        object.__setattr__(
            self,
            "version",
            _required_text(self.version, "version"),
        )


@dataclass(frozen=True)
class AgentRegistrationRequest:
    """One prebuilt agent package submitted by an application."""

    agent_id: str
    version: str
    definition_root: Path

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "agent_id",
            _required_text(self.agent_id, "agent_id"),
        )
        object.__setattr__(
            self,
            "version",
            _required_text(self.version, "version"),
        )

        root = Path(self.definition_root).expanduser()
        if not str(root).strip():
            raise AgentRegistrationValidationError(
                "definition_root must not be empty"
            )
        object.__setattr__(self, "definition_root", root)


@dataclass(frozen=True)
class BulkAgentRegistrationRequest:
    """Atomic bulk registration submitted by one trusted application."""

    application_id: str
    agents: tuple[AgentRegistrationRequest, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "application_id",
            _required_text(self.application_id, "application_id"),
        )
        object.__setattr__(self, "agents", tuple(self.agents))

        if not self.agents:
            raise AgentRegistrationValidationError(
                "Bulk registration must contain at least one agent"
            )

        keys = [(agent.agent_id, agent.version) for agent in self.agents]
        if len(keys) != len(set(keys)):
            raise AgentRegistrationValidationError(
                "Bulk registration contains duplicate agent ID and version"
            )


@dataclass(frozen=True)
class AgentRegistrationRecord:
    """Validated registration stored by the framework catalog."""

    key: AgentRegistrationKey
    definition_root: Path
    definition_fingerprint: str
    registered_at: datetime

    @classmethod
    def create(
        cls,
        *,
        application_id: str,
        request: AgentRegistrationRequest,
        definition_fingerprint: str,
    ) -> "AgentRegistrationRecord":
        return cls(
            key=AgentRegistrationKey(
                application_id=application_id,
                agent_id=request.agent_id,
                version=request.version,
            ),
            definition_root=request.definition_root.resolve(),
            definition_fingerprint=_required_text(
                definition_fingerprint,
                "definition_fingerprint",
            ),
            registered_at=datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class BulkAgentRegistrationResult:
    """Result returned after one atomic registration transaction."""

    application_id: str
    status: RegistrationStatus
    registrations: tuple[AgentRegistrationRecord, ...]


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentRegistrationValidationError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()
