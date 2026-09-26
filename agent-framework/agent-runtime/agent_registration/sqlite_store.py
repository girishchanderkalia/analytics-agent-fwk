"""SQLite draft storage for the agent-registration control plane."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .errors import AgentDraftConflictError, AgentDraftNotFoundError
from .models import (
    AgentBundleDocument,
    AgentDocumentType,
    AgentDraft,
    ValidationIssue,
    ValidationResult,
)


class SQLiteAgentDraftStore:
    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create(
        self,
        *,
        agent_id: str,
        display_name: str,
        description: str,
        documents: tuple[AgentBundleDocument, ...],
        validation: ValidationResult,
    ) -> AgentDraft:
        draft_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO agent_drafts (
                        draft_id, agent_id, display_name, description,
                        status, validation_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        draft_id, agent_id, display_name, description,
                        "draft", json.dumps(validation.to_dict()), now, now,
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO agent_draft_documents (
                        draft_id, document_type, file_name, content
                    ) VALUES (?, ?, ?, ?)
                    """,
                    [
                        (draft_id, item.document_type.value, item.file_name, item.content)
                        for item in documents
                    ],
                )
        except sqlite3.IntegrityError as exc:
            raise AgentDraftConflictError("Agent draft could not be created") from exc
        return self.get(agent_id=agent_id, draft_id=draft_id)

    def get(self, *, agent_id: str, draft_id: str) -> AgentDraft:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_drafts WHERE agent_id = ? AND draft_id = ?",
                (agent_id, draft_id),
            ).fetchone()
            if row is None:
                raise AgentDraftNotFoundError(f"Agent draft not found: {draft_id}")
            document_rows = connection.execute(
                "SELECT * FROM agent_draft_documents WHERE draft_id = ? ORDER BY file_name",
                (draft_id,),
            ).fetchall()
        raw_validation = json.loads(row["validation_json"])
        validation = ValidationResult(
            errors=tuple(_issue(item) for item in raw_validation.get("errors", [])),
            warnings=tuple(_issue(item) for item in raw_validation.get("warnings", [])),
        )
        return AgentDraft(
            draft_id=row["draft_id"],
            agent_id=row["agent_id"],
            display_name=row["display_name"],
            description=row["description"],
            status=row["status"],
            documents=tuple(
                AgentBundleDocument(
                    document_type=AgentDocumentType(item["document_type"]),
                    file_name=item["file_name"],
                    content=item["content"],
                )
                for item in document_rows
            ),
            validation=validation,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_drafts (
                    draft_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    validation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_draft_documents (
                    draft_id TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    PRIMARY KEY (draft_id, document_type),
                    FOREIGN KEY (draft_id) REFERENCES agent_drafts(draft_id)
                )
                """
            )


def _issue(value: dict) -> ValidationIssue:
    return ValidationIssue(
        code=value["code"],
        message=value["message"],
        severity=value.get("severity", "error"),
        document_type=value.get("documentType"),
        file_name=value.get("fileName"),
        path=value.get("path"),
        line=value.get("line"),
    )
