"""Persistence models for Agent Runtime conversations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping
from uuid import uuid4


class ConversationStatus(StrEnum):
    """Persisted conversation execution status."""

    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ConversationStoreError(RuntimeError):
    """Base error raised by conversation persistence."""


class ConversationNotFoundError(ConversationStoreError):
    """Raised when a conversation does not exist."""


class ConversationConflictError(ConversationStoreError):
    """Raised when optimistic locking detects a conflict."""


class InvalidConversationError(ConversationStoreError):
    """Raised when a conversation record is invalid."""


@dataclass(frozen=True)
class ConversationRecord:
    """Durable representation of one agent conversation."""

    conversation_id: str
    agent_id: str
    status: ConversationStatus
    current_node: str | None
    state: dict[str, Any]
    pending_approval: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def create(
        cls,
        *,
        agent_id: str,
        state: Mapping[str, Any],
        status: ConversationStatus = ConversationStatus.RUNNING,
        current_node: str | None = None,
        pending_approval: Mapping[str, Any] | None = None,
        conversation_id: str | None = None,
    ) -> "ConversationRecord":
        """Create a new conversation record."""

        normalized_agent_id = _non_empty_string(
            agent_id,
            field_name="agent_id",
        )

        if conversation_id is None:
            identifier = str(uuid4())
        else:
            identifier = _non_empty_string(
                conversation_id,
                field_name="conversation_id",
            )

        if not isinstance(status, ConversationStatus):
            raise InvalidConversationError(
                "status must be a ConversationStatus"
            )

        if current_node is not None:
            current_node = _non_empty_string(
                current_node,
                field_name="current_node",
            )

        if not isinstance(state, Mapping):
            raise InvalidConversationError(
                "state must be a mapping"
            )

        if pending_approval is not None and not isinstance(
            pending_approval,
            Mapping,
        ):
            raise InvalidConversationError(
                "pending_approval must be a mapping or None"
            )

        now = datetime.now(timezone.utc)

        return cls(
            conversation_id=identifier,
            agent_id=normalized_agent_id,
            status=status,
            current_node=current_node,
            state=dict(state),
            pending_approval=(
                dict(pending_approval)
                if pending_approval is not None
                else None
            ),
            created_at=now,
            updated_at=now,
            version=1,
        )


def _non_empty_string(
    value: Any,
    *,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidConversationError(
            f"{field_name} must be a non-empty string"
        )

    return value.strip()
