from __future__ import annotations

import sys
from pathlib import Path

import pytest


V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))

from persistence.persistence_models import (  # noqa: E402
    ConversationConflictError,
    ConversationNotFoundError,
    ConversationStatus,
    InvalidConversationError,
)
from persistence.sqlite_conversation_store import (  # noqa: E402
    SQLiteConversationStore,
)


@pytest.fixture
def store(tmp_path: Path) -> SQLiteConversationStore:
    return SQLiteConversationStore(
        tmp_path / "conversations.sqlite"
    )


def test_creates_conversation(store: SQLiteConversationStore) -> None:
    record = store.create(
        agent_id="opo-monitoring-agent",
        state={"question": "Show recent trends"},
        status=ConversationStatus.RUNNING,
    )

    assert record.conversation_id
    assert record.agent_id == "opo-monitoring-agent"
    assert record.status is ConversationStatus.RUNNING
    assert record.current_node is None
    assert record.version == 1
    assert record.state == {"question": "Show recent trends"}


def test_gets_conversation(store: SQLiteConversationStore) -> None:
    created = store.create(
        agent_id="opo-monitoring-agent",
        state={"question": "Show recent trends"},
        status=ConversationStatus.RUNNING,
    )
    loaded = store.get(created.conversation_id)
    assert loaded == created


def test_creates_conversation_with_explicit_id(
    store: SQLiteConversationStore,
) -> None:
    record = store.create(
        conversation_id="conversation-1",
        agent_id="opo-monitoring-agent",
        state={},
        status=ConversationStatus.RUNNING,
    )
    assert record.conversation_id == "conversation-1"


def test_duplicate_conversation_is_rejected(
    store: SQLiteConversationStore,
) -> None:
    store.create(
        conversation_id="conversation-1",
        agent_id="opo-monitoring-agent",
        state={},
        status=ConversationStatus.RUNNING,
    )

    with pytest.raises(
        ConversationConflictError,
        match="already exists",
    ):
        store.create(
            conversation_id="conversation-1",
            agent_id="opo-monitoring-agent",
            state={},
            status=ConversationStatus.RUNNING,
        )


def test_updates_conversation(store: SQLiteConversationStore) -> None:
    created = store.create(
        agent_id="opo-monitoring-agent",
        state={"status": "running"},
        status=ConversationStatus.RUNNING,
    )

    updated = store.update(
        conversation_id=created.conversation_id,
        expected_version=created.version,
        state={"status": "waiting_for_approval"},
        status=ConversationStatus.WAITING_FOR_APPROVAL,
        current_node="approve_investigation",
        pending_approval={
            "approval_id": "investigate_selected_outlier"
        },
    )

    assert updated.version == 2
    assert updated.status is ConversationStatus.WAITING_FOR_APPROVAL
    assert updated.current_node == "approve_investigation"
    assert updated.pending_approval == {
        "approval_id": "investigate_selected_outlier"
    }


def test_stale_version_is_rejected(
    store: SQLiteConversationStore,
) -> None:
    created = store.create(
        agent_id="opo-monitoring-agent",
        state={},
        status=ConversationStatus.RUNNING,
    )

    store.update(
        conversation_id=created.conversation_id,
        expected_version=1,
        state={"value": 1},
        status=ConversationStatus.RUNNING,
        current_node=None,
        pending_approval=None,
    )

    with pytest.raises(
        ConversationConflictError,
        match="version conflict",
    ):
        store.update(
            conversation_id=created.conversation_id,
            expected_version=1,
            state={"value": 2},
            status=ConversationStatus.RUNNING,
            current_node=None,
            pending_approval=None,
        )


def test_missing_conversation_is_rejected(
    store: SQLiteConversationStore,
) -> None:
    with pytest.raises(
        ConversationNotFoundError,
        match="not found",
    ):
        store.get("missing-conversation")


def test_exists(store: SQLiteConversationStore) -> None:
    created = store.create(
        agent_id="opo-monitoring-agent",
        state={},
        status=ConversationStatus.RUNNING,
    )

    assert store.exists(created.conversation_id)
    assert not store.exists("missing-conversation")


def test_deletes_conversation(store: SQLiteConversationStore) -> None:
    created = store.create(
        agent_id="opo-monitoring-agent",
        state={},
        status=ConversationStatus.RUNNING,
    )

    store.delete(created.conversation_id)
    assert not store.exists(created.conversation_id)


def test_delete_missing_conversation_is_rejected(
    store: SQLiteConversationStore,
) -> None:
    with pytest.raises(
        ConversationNotFoundError,
        match="not found",
    ):
        store.delete("missing-conversation")


def test_state_must_be_json_serializable(
    store: SQLiteConversationStore,
) -> None:
    with pytest.raises(
        InvalidConversationError,
        match="JSON serializable",
    ):
        store.create(
            agent_id="opo-monitoring-agent",
            state={"invalid": object()},
            status=ConversationStatus.RUNNING,
        )


def test_empty_conversation_id_is_rejected(
    store: SQLiteConversationStore,
) -> None:
    with pytest.raises(
        InvalidConversationError,
        match="non-empty",
    ):
        store.get("   ")
