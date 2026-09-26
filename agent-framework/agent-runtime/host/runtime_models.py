"""Application-facing commands and responses for the Agent Runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


class RuntimeServiceError(RuntimeError):
    """Base error raised by the Runtime Service."""


class InvalidRuntimeCommandError(RuntimeServiceError):
    """Raised when a chat or resume command is invalid."""


class ConversationStateError(RuntimeServiceError):
    """Raised when a conversation cannot perform the requested transition."""


@dataclass(frozen=True)
class ChatCommand:
    """Start a new application-agent conversation."""

    agent_id: str
    message: str
    user_id: str | None = None
    application_context: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        _require_non_empty(self.agent_id, "agent_id")
        _require_non_empty(self.message, "message")

        if self.user_id is not None:
            _require_non_empty(self.user_id, "user_id")

        if not isinstance(self.application_context, Mapping):
            raise InvalidRuntimeCommandError(
                "application_context must be a mapping"
            )


@dataclass(frozen=True)
class ResumeCommand:
    """Resume a conversation waiting for analyst approval."""

    conversation_id: str
    approved: bool
    selected_outlier_id: str | None = None
    comment: str | None = None
    expected_version: int | None = None
    values: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        _require_non_empty(self.conversation_id, "conversation_id")

        if not isinstance(self.approved, bool):
            raise InvalidRuntimeCommandError(
                "approved must be a boolean"
            )

        if self.selected_outlier_id is not None:
            _require_non_empty(
                self.selected_outlier_id,
                "selected_outlier_id",
            )

        if self.comment is not None and not isinstance(self.comment, str):
            raise InvalidRuntimeCommandError(
                "comment must be a string or None"
            )

        if self.expected_version is not None:
            if (
                not isinstance(self.expected_version, int)
                or self.expected_version < 1
            ):
                raise InvalidRuntimeCommandError(
                    "expected_version must be a positive integer"
                )

        if not isinstance(self.values, Mapping):
            raise InvalidRuntimeCommandError(
                "values must be a mapping"
            )


@dataclass(frozen=True)
class RuntimeResponse:
    """Public response returned to the Analytics Copilot Service."""

    conversation_id: str
    agent_id: str
    status: str
    version: int
    result: dict[str, Any]
    approval_request: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a transport-friendly public representation."""

        return {
            "conversationId": self.conversation_id,
            "agentId": self.agent_id,
            "status": self.status,
            "version": self.version,
            "result": dict(self.result),
            "approvalRequest": (
                dict(self.approval_request)
                if self.approval_request is not None
                else None
            ),
        }


def _require_non_empty(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidRuntimeCommandError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()
