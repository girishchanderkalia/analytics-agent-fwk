"""Transport-neutral models for the migrated Runtime Service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .errors import RuntimeServiceValidationError


@dataclass(frozen=True)
class RuntimeServiceStartRequest:
    application_id: str
    agent_id: str
    version: str
    conversation_id: str
    initial_state: Mapping[str, Any]

    def __post_init__(self) -> None:
        _validate_identity(self)
        if not isinstance(self.initial_state, Mapping):
            raise RuntimeServiceValidationError(
                "initial_state must be a mapping"
            )
        object.__setattr__(self, "initial_state", dict(self.initial_state))


@dataclass(frozen=True)
class RuntimeServiceResumeRequest:
    application_id: str
    agent_id: str
    version: str
    conversation_id: str
    resume_value: Any
    interrupt_id: str | None = None

    def __post_init__(self) -> None:
        _validate_identity(self)
        if self.interrupt_id is not None:
            object.__setattr__(
                self,
                "interrupt_id",
                _required_text(self.interrupt_id, "interrupt_id"),
            )
        if self.resume_value is None:
            raise RuntimeServiceValidationError(
                "resume_value must not be None"
            )


@dataclass(frozen=True)
class RuntimeServiceStateRequest:
    application_id: str
    agent_id: str
    version: str
    conversation_id: str

    def __post_init__(self) -> None:
        _validate_identity(self)


@dataclass(frozen=True)
class RuntimeInterrupt:
    interrupt_id: str
    value: Any


@dataclass(frozen=True)
class RuntimeServiceResult:
    application_id: str
    agent_id: str
    version: str
    conversation_id: str
    status: str
    state: Mapping[str, Any]
    interrupts: tuple[RuntimeInterrupt, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", dict(self.state))
        object.__setattr__(self, "interrupts", tuple(self.interrupts))


def _validate_identity(instance: object) -> None:
    for field_name in (
        "application_id",
        "agent_id",
        "version",
        "conversation_id",
    ):
        object.__setattr__(
            instance,
            field_name,
            _required_text(getattr(instance, field_name), field_name),
        )


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeServiceValidationError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()
