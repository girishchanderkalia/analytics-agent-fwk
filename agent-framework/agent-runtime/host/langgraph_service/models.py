"""Public command and response models for the LangGraph Runtime Service."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping

@dataclass(frozen=True)
class AgentVersionReference:
    agent_id: str
    version: str
    definition_digest: str
    definition: Any

@dataclass(frozen=True)
class LangGraphChatCommand:
    agent_id: str
    message: str
    agent_version: str | None = None
    user_id: str | None = None
    application_context: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class LangGraphResumeCommand:
    conversation_id: str
    approved: bool
    selected_outlier_id: str | None = None
    comment: str | None = None
    values: Mapping[str, Any] = field(default_factory=dict)
    expected_version: int | None = None

@dataclass(frozen=True)
class LangGraphRuntimeResponse:
    conversation_id: str
    agent_id: str
    agent_version: str
    status: str
    version: int
    result: Mapping[str, Any]
    approval_request: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversationId": self.conversation_id,
            "agentId": self.agent_id,
            "agentVersion": self.agent_version,
            "status": self.status,
            "version": self.version,
            "result": dict(self.result),
            "approvalRequest": (
                dict(self.approval_request)
                if self.approval_request is not None else None
            ),
        }
