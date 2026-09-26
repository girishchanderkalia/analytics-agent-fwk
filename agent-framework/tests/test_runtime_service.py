from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pytest


V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))

from execution.execution_models import (  # noqa: E402
    ApprovalRequest,
    ExecutionStatus,
    ResumeInput,
    WorkflowExecutionResult,
)
from host.runtime_models import (  # noqa: E402
    ChatCommand,
    ConversationStateError,
    InvalidRuntimeCommandError,
    ResumeCommand,
)
from host.runtime_service import RuntimeService  # noqa: E402
from persistence.persistence_models import (  # noqa: E402
    ConversationStatus,
)
from persistence.sqlite_conversation_store import (  # noqa: E402
    SQLiteConversationStore,
)


@dataclass
class FakeDocument:
    metadata: dict[str, Any]


@dataclass
class FakeBundle:
    agent_id: str
    state: FakeDocument


class FakeRepository:
    def __init__(self) -> None:
        self.bundle = FakeBundle(
            agent_id="opo-monitoring-agent",
            state=FakeDocument(
                metadata={
                    "fields": {
                        "conversation_id": {},
                        "agent_id": {},
                        "user_id": {},
                        "question": {},
                        "application_context": {},
                    }
                }
            ),
        )

    def load(self, agent_reference: str) -> FakeBundle:
        if agent_reference in {
            "opo-monitoring",
            "opo-monitoring-agent",
        }:
            return self.bundle
        raise KeyError(agent_reference)

    def load_all(self) -> Mapping[str, FakeBundle]:
        return {self.bundle.agent_id: self.bundle}


class FakeEngine:
    def __init__(self, bundle: FakeBundle) -> None:
        self.bundle = bundle
        self.last_initial_state: dict[str, Any] | None = None
        self.last_resume_input: ResumeInput | None = None

    def run(
        self,
        initial_state: Mapping[str, Any] | None = None,
    ) -> WorkflowExecutionResult:
        state = dict(initial_state or {})
        self.last_initial_state = state

        if "outlier" in state.get("question", "").lower():
            state.update(
                {
                    "status": "waiting_for_approval",
                    "detected_outliers": [{"id": "outlier-1"}],
                    "pending_approval": {
                        "approval_id": "investigate_selected_outlier"
                    },
                }
            )
            approval = ApprovalRequest(
                approval_id="investigate_selected_outlier",
                node_id="approve_investigation",
                public_type="approval_required",
                request_contract="InvestigationApproval",
                payload={"detected_outliers": [{"id": "outlier-1"}]},
            )
            return WorkflowExecutionResult(
                status=ExecutionStatus.WAITING_FOR_APPROVAL,
                state=state,
                current_node="approve_investigation",
                approval_request=approval,
            )

        state.update(
            {
                "status": "completed",
                "findings": {"finding": "No outliers"},
            }
        )
        return WorkflowExecutionResult(
            status=ExecutionStatus.COMPLETED,
            state=state,
            current_node=None,
        )

    def resume(
        self,
        *,
        state: Mapping[str, Any],
        current_node: str,
        resume_input: ResumeInput,
    ) -> WorkflowExecutionResult:
        self.last_resume_input = resume_input
        updated = dict(state)
        updated["pending_approval"] = None

        if resume_input.approved:
            updated.update(
                {
                    "status": "completed",
                    "selected_outlier": {
                        "id": resume_input.selected_outlier_id
                    },
                    "findings": {"finding": "Investigation completed"},
                }
            )
            return WorkflowExecutionResult(
                status=ExecutionStatus.COMPLETED,
                state=updated,
                current_node=None,
            )

        updated["status"] = "cancelled"
        return WorkflowExecutionResult(
            status=ExecutionStatus.CANCELLED,
            state=updated,
            current_node=None,
        )


@pytest.fixture
def setup_service(tmp_path: Path):
    repository = FakeRepository()
    store = SQLiteConversationStore(tmp_path / "runtime.sqlite")
    engines: list[FakeEngine] = []

    def engine_factory(bundle: FakeBundle) -> FakeEngine:
        engine = FakeEngine(bundle)
        engines.append(engine)
        return engine

    service = RuntimeService(
        agent_repository=repository,
        conversation_store=store,
        engine_factory=engine_factory,
    )
    return service, store, engines


def test_start_chat_completes_and_persists(setup_service) -> None:
    service, store, engines = setup_service
    response = service.start_chat(
        ChatCommand(
            agent_id="opo-monitoring-agent",
            message="Show recent trends",
            user_id="user-1",
            application_context={"source": "opo"},
        )
    )

    assert response.status == "completed"
    assert response.version == 1
    assert response.result["findings"]["finding"] == "No outliers"
    assert store.exists(response.conversation_id)
    assert engines[0].last_initial_state["question"] == "Show recent trends"


def test_start_chat_persists_approval_interruption(setup_service) -> None:
    service, store, _ = setup_service
    response = service.start_chat(
        ChatCommand(
            agent_id="opo-monitoring-agent",
            message="Show an outlier",
        )
    )

    assert response.status == "waiting_for_approval"
    assert response.approval_request is not None
    record = store.get(response.conversation_id)
    assert record.current_node == "approve_investigation"
    assert record.status is ConversationStatus.WAITING_FOR_APPROVAL


def test_approved_resume_completes(setup_service) -> None:
    service, store, _ = setup_service
    started = service.start_chat(
        ChatCommand(
            agent_id="opo-monitoring-agent",
            message="Show an outlier",
        )
    )

    resumed = service.resume(
        ResumeCommand(
            conversation_id=started.conversation_id,
            approved=True,
            selected_outlier_id="outlier-1",
            expected_version=started.version,
        )
    )

    assert resumed.status == "completed"
    assert resumed.version == 2
    assert resumed.result["findings"]["finding"] == "Investigation completed"
    assert store.get(resumed.conversation_id).current_node is None


def test_rejected_resume_cancels(setup_service) -> None:
    service, _, _ = setup_service
    started = service.start_chat(
        ChatCommand(
            agent_id="opo-monitoring-agent",
            message="Show an outlier",
        )
    )
    resumed = service.resume(
        ResumeCommand(
            conversation_id=started.conversation_id,
            approved=False,
        )
    )
    assert resumed.status == "cancelled"


def test_completed_conversation_cannot_resume(setup_service) -> None:
    service, _, _ = setup_service
    started = service.start_chat(
        ChatCommand(
            agent_id="opo-monitoring-agent",
            message="Show recent trends",
        )
    )

    with pytest.raises(
        ConversationStateError,
        match="not waiting for approval",
    ):
        service.resume(
            ResumeCommand(
                conversation_id=started.conversation_id,
                approved=True,
            )
        )


def test_stale_expected_version_is_rejected(setup_service) -> None:
    service, _, _ = setup_service
    started = service.start_chat(
        ChatCommand(
            agent_id="opo-monitoring-agent",
            message="Show an outlier",
        )
    )

    with pytest.raises(
        ConversationStateError,
        match="version",
    ):
        service.resume(
            ResumeCommand(
                conversation_id=started.conversation_id,
                approved=True,
                selected_outlier_id="outlier-1",
                expected_version=99,
            )
        )


def test_empty_message_is_rejected(setup_service) -> None:
    service, _, _ = setup_service
    with pytest.raises(
        InvalidRuntimeCommandError,
        match="message",
    ):
        service.start_chat(
            ChatCommand(
                agent_id="opo-monitoring-agent",
                message="   ",
            )
        )


def test_public_response_hides_runtime_internals(setup_service) -> None:
    service, _, _ = setup_service
    response = service.start_chat(
        ChatCommand(
            agent_id="opo-monitoring-agent",
            message="Show recent trends",
        )
    )
    public = response.to_dict()

    assert "currentNode" not in public
    assert "threadId" not in public
    assert "sessionId" not in public
    assert "checkpointId" not in public
    assert "current_node" not in response.result
    assert "thread_id" not in response.result
    assert "session_id" not in response.result
    assert "checkpoint_id" not in response.result


def test_get_conversation_returns_public_response(setup_service) -> None:
    service, _, _ = setup_service
    started = service.start_chat(
        ChatCommand(
            agent_id="opo-monitoring-agent",
            message="Show recent trends",
        )
    )
    loaded = service.get_conversation(started.conversation_id)
    assert loaded == started
