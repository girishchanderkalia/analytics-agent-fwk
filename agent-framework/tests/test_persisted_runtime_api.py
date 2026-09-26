"""FastAPI tests for persisted conversation endpoints."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))


from persistence.persistence_models import (  # noqa: E402
    ConversationConflictError,
    ConversationNotFoundError,
)
from runtime_api import create_app  # noqa: E402


@dataclass(frozen=True)
class FakeRuntimeResponse:
    conversation_id: str
    agent_id: str
    status: str
    version: int
    result: dict[str, Any]
    approval_request: dict[str, Any] | None = None


class FakeRuntimeService:
    def __init__(self) -> None:
        self.chat_commands: list[Any] = []
        self.resume_commands: list[Any] = []

    def start_chat(self, command: Any) -> FakeRuntimeResponse:
        self.chat_commands.append(command)
        return FakeRuntimeResponse(
            conversation_id="conversation-1",
            agent_id=command.agent_id,
            status="waiting_for_approval",
            version=1,
            result={"question": command.message},
            approval_request={
                "approval_id": "investigate_outlier",
                "node_id": "approve_investigation",
                "public_type": "approval_required",
            },
        )

    def resume(self, command: Any) -> FakeRuntimeResponse:
        self.resume_commands.append(command)

        if command.expected_version == 99:
            raise ConversationConflictError("Conversation version conflict")

        return FakeRuntimeResponse(
            conversation_id=command.conversation_id,
            agent_id="opo-monitoring-agent",
            status="completed",
            version=2,
            result={"findings": {"finding": "Completed"}},
        )

    def get_conversation(self, conversation_id: str) -> FakeRuntimeResponse:
        if conversation_id == "missing":
            raise ConversationNotFoundError(
                "Conversation does not exist: missing"
            )

        return FakeRuntimeResponse(
            conversation_id=conversation_id,
            agent_id="opo-monitoring-agent",
            status="waiting_for_approval",
            version=1,
            result={"outliers": [{"id": "outlier-1"}]},
        )


def test_health_endpoint() -> None:
    response = TestClient(create_app(FakeRuntimeService())).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_creates_persisted_conversation() -> None:
    service = FakeRuntimeService()
    response = TestClient(create_app(service)).post(
        "/v1/chat",
        json={
            "agent_id": "opo-monitoring-agent",
            "message": "Show trends and outliers",
            "application_context": {"lookback_days": 30},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == "conversation-1"
    assert body["version"] == 1
    assert body["status"] == "waiting_for_approval"
    assert service.chat_commands[0].message == "Show trends and outliers"


def test_resume_uses_conversation_id_and_revision() -> None:
    service = FakeRuntimeService()
    response = TestClient(create_app(service)).post(
        "/v1/conversations/conversation-1/resume",
        json={
            "approved": True,
            "selected_outlier_id": "outlier-1",
            "expected_version": 1,
            "comment": "Proceed",
            "values": {},
        },
    )

    assert response.status_code == 200
    assert response.json()["version"] == 2
    command = service.resume_commands[0]
    assert command.conversation_id == "conversation-1"
    assert command.expected_version == 1
    assert command.approved is True


def test_resume_payload_does_not_accept_workflow_state() -> None:
    response = TestClient(create_app(FakeRuntimeService())).post(
        "/v1/conversations/conversation-1/resume",
        json={
            "approved": True,
            "state": {"should_not": "be accepted"},
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"


def test_get_conversation_returns_latest_checkpoint() -> None:
    response = TestClient(create_app(FakeRuntimeService())).get(
        "/v1/conversations/conversation-1"
    )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "conversation-1"
    assert response.json()["result"]["outliers"][0]["id"] == "outlier-1"


def test_unknown_conversation_maps_to_404() -> None:
    response = TestClient(create_app(FakeRuntimeService())).get(
        "/v1/conversations/missing"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_not_found"


def test_revision_conflict_maps_to_409() -> None:
    response = TestClient(create_app(FakeRuntimeService())).post(
        "/v1/conversations/conversation-1/resume",
        json={
            "approved": True,
            "expected_version": 99,
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conversation_version_conflict"


def test_missing_runtime_service_maps_to_503() -> None:
    response = TestClient(create_app()).get(
        "/v1/conversations/conversation-1"
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "runtime_service_unavailable"
