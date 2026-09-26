"""Conversation persistence abstraction."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from .persistence_models import (
    ConversationRecord,
    ConversationStatus,
)


class ConversationStore(Protocol):
    """Durable storage interface for agent conversations."""

    def create(
        self,
        *,
        agent_id: str,
        state: Mapping[str, Any],
        status: ConversationStatus,
        current_node: str | None = None,
        pending_approval: Mapping[str, Any] | None = None,
        conversation_id: str | None = None,
    ) -> ConversationRecord:
        """Create and persist a conversation."""
        ...

    def get(
        self,
        conversation_id: str,
    ) -> ConversationRecord:
        """Retrieve one conversation."""
        ...

    def update(
        self,
        *,
        conversation_id: str,
        expected_version: int,
        state: Mapping[str, Any],
        status: ConversationStatus,
        current_node: str | None,
        pending_approval: Mapping[str, Any] | None,
    ) -> ConversationRecord:
        """Update a conversation using optimistic locking."""
        ...

    def delete(
        self,
        conversation_id: str,
    ) -> None:
        """Delete a conversation."""
        ...

    def exists(
        self,
        conversation_id: str,
    ) -> bool:
        """Return whether a conversation exists."""
        ...
