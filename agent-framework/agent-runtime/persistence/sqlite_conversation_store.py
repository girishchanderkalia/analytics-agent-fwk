"""SQLite implementation of the conversation store."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .persistence_models import (
    ConversationConflictError,
    ConversationNotFoundError,
    ConversationRecord,
    ConversationStatus,
    InvalidConversationError,
)


class SQLiteConversationStore:
    """Persist agent conversations in SQLite."""

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

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

        record = ConversationRecord.create(
            agent_id=agent_id,
            state=state,
            status=status,
            current_node=current_node,
            pending_approval=pending_approval,
            conversation_id=conversation_id,
        )

        with self._connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO conversations (
                        conversation_id,
                        agent_id,
                        status,
                        current_node,
                        state_json,
                        pending_approval_json,
                        created_at,
                        updated_at,
                        version
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.conversation_id,
                        record.agent_id,
                        record.status.value,
                        record.current_node,
                        _serialize(record.state),
                        _serialize_optional(record.pending_approval),
                        _serialize_datetime(record.created_at),
                        _serialize_datetime(record.updated_at),
                        record.version,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConversationConflictError(
                    "Conversation already exists: "
                    f"{record.conversation_id}"
                ) from exc

        return record

    def get(self, conversation_id: str) -> ConversationRecord:
        """Retrieve one conversation."""

        identifier = _validate_identifier(conversation_id)

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    conversation_id,
                    agent_id,
                    status,
                    current_node,
                    state_json,
                    pending_approval_json,
                    created_at,
                    updated_at,
                    version
                FROM conversations
                WHERE conversation_id = ?
                """,
                (identifier,),
            ).fetchone()

        if row is None:
            raise ConversationNotFoundError(
                f"Conversation not found: {identifier}"
            )

        return _row_to_record(row)

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

        identifier = _validate_identifier(conversation_id)

        if not isinstance(expected_version, int) or expected_version < 1:
            raise InvalidConversationError(
                "expected_version must be a positive integer"
            )

        if not isinstance(status, ConversationStatus):
            raise InvalidConversationError(
                "status must be a ConversationStatus"
            )

        if not isinstance(state, Mapping):
            raise InvalidConversationError(
                "state must be a mapping"
            )

        updated_at = datetime.now(timezone.utc)
        next_version = expected_version + 1

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE conversations
                SET
                    status = ?,
                    current_node = ?,
                    state_json = ?,
                    pending_approval_json = ?,
                    updated_at = ?,
                    version = ?
                WHERE conversation_id = ?
                  AND version = ?
                """,
                (
                    status.value,
                    current_node,
                    _serialize(dict(state)),
                    _serialize_optional(pending_approval),
                    _serialize_datetime(updated_at),
                    next_version,
                    identifier,
                    expected_version,
                ),
            )

            if cursor.rowcount == 0:
                existing = connection.execute(
                    """
                    SELECT version
                    FROM conversations
                    WHERE conversation_id = ?
                    """,
                    (identifier,),
                ).fetchone()

                if existing is None:
                    raise ConversationNotFoundError(
                        f"Conversation not found: {identifier}"
                    )

                raise ConversationConflictError(
                    "Conversation version conflict for "
                    f"{identifier}. Expected {expected_version}, "
                    f"actual {existing['version']}"
                )

        return self.get(identifier)

    def delete(self, conversation_id: str) -> None:
        """Delete a conversation."""

        identifier = _validate_identifier(conversation_id)

        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM conversations
                WHERE conversation_id = ?
                """,
                (identifier,),
            )

        if cursor.rowcount == 0:
            raise ConversationNotFoundError(
                f"Conversation not found: {identifier}"
            )

    def exists(self, conversation_id: str) -> bool:
        """Return whether a conversation exists."""

        identifier = _validate_identifier(conversation_id)

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM conversations
                WHERE conversation_id = ?
                """,
                (identifier,),
            ).fetchone()

        return row is not None

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=10,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_node TEXT NULL,
                    state_json TEXT NOT NULL,
                    pending_approval_json TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL CHECK (version >= 1)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversations_agent_id
                ON conversations (agent_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversations_status
                ON conversations (status)
                """
            )


def _row_to_record(row: sqlite3.Row) -> ConversationRecord:
    return ConversationRecord(
        conversation_id=row["conversation_id"],
        agent_id=row["agent_id"],
        status=ConversationStatus(row["status"]),
        current_node=row["current_node"],
        state=_deserialize(row["state_json"]),
        pending_approval=_deserialize_optional(
            row["pending_approval_json"]
        ),
        created_at=_deserialize_datetime(row["created_at"]),
        updated_at=_deserialize_datetime(row["updated_at"]),
        version=int(row["version"]),
    )


def _serialize(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            value,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise InvalidConversationError(
            "Conversation value is not JSON serializable"
        ) from exc


def _serialize_optional(value: Mapping[str, Any] | None) -> str | None:
    if value is None:
        return None
    return _serialize(value)


def _deserialize(value: str) -> dict[str, Any]:
    try:
        result = json.loads(value)
    except json.JSONDecodeError as exc:
        raise InvalidConversationError(
            "Stored conversation JSON is invalid"
        ) from exc

    if not isinstance(result, dict):
        raise InvalidConversationError(
            "Stored conversation JSON must be an object"
        )

    return result


def _deserialize_optional(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return _deserialize(value)


def _serialize_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _deserialize_datetime(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise InvalidConversationError(
            f"Stored datetime is invalid: {value!r}"
        ) from exc

    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)

    return result


def _validate_identifier(conversation_id: Any) -> str:
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise InvalidConversationError(
            "conversation_id must be a non-empty string"
        )
    return conversation_id.strip()
