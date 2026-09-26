"""Immutable request and result models for central LangGraph execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .runtime_errors import AgentRuntimeError, InvalidResumeRequestError


class AgentRuntimeStatus(StrEnum):
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


@dataclass(frozen=True, order=True)
class CompiledGraphKey:
    application_id: str
    agent_id: str
    version: str
    definition_fingerprint: str

    def __post_init__(self) -> None:
        for field_name in (
            "application_id",
            "agent_id",
            "version",
            "definition_fingerprint",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True)
class AgentInterrupt:
    """Serializable interrupt surfaced by LangGraph execution."""

    interrupt_id: str
    value: Any

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "interrupt_id",
            _required_text(self.interrupt_id, "interrupt_id"),
        )


@dataclass(frozen=True)
class AgentRuntimeStartRequest:
    application_id: str
    agent_id: str
    version: str
    thread_id: str
    initial_state: Mapping[str, Any]

    def __post_init__(self) -> None:
        _validate_identity(self)
        if not isinstance(self.initial_state, Mapping):
            raise AgentRuntimeError("initial_state must be a mapping")
        object.__setattr__(self, "initial_state", dict(self.initial_state))


@dataclass(frozen=True)
class AgentRuntimeResumeRequest:
    application_id: str
    agent_id: str
    version: str
    thread_id: str
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
            raise InvalidResumeRequestError(
                "resume_value must not be None"
            )


@dataclass(frozen=True)
class AgentRuntimeStateRequest:
    application_id: str
    agent_id: str
    version: str
    thread_id: str

    def __post_init__(self) -> None:
        _validate_identity(self)


@dataclass(frozen=True)
class AgentRuntimeResult:
    application_id: str
    agent_id: str
    version: str
    thread_id: str
    state: Mapping[str, Any]
    status: AgentRuntimeStatus = AgentRuntimeStatus.COMPLETED
    interrupts: tuple[AgentInterrupt, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.state, Mapping):
            raise AgentRuntimeError("state must be a mapping")
        object.__setattr__(self, "state", dict(self.state))
        object.__setattr__(self, "interrupts", tuple(self.interrupts))
        if self.status is AgentRuntimeStatus.INTERRUPTED and not self.interrupts:
            raise AgentRuntimeError(
                "Interrupted runtime results require interrupt details"
            )


def _validate_identity(instance: object) -> None:
    for field_name in (
        "application_id",
        "agent_id",
        "version",
        "thread_id",
    ):
        object.__setattr__(
            instance,
            field_name,
            _required_text(getattr(instance, field_name), field_name),
        )


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentRuntimeError(f"{field_name} must be a non-empty string")
    return value.strip()
