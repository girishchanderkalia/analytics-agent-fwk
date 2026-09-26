
"""Public and internal models used by the workflow execution engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class ExecutionStatus(StrEnum):
    """Externally meaningful execution statuses."""

    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class NodeType(StrEnum):
    """Supported declarative workflow-node types."""

    MODEL = "model"
    CAPABILITY = "capability"
    OPERATION = "operation"
    DETERMINISTIC = "deterministic"
    APPROVAL = "approval"


@dataclass(frozen=True)
class ApprovalRequest:
    """Approval request returned when workflow execution is interrupted."""

    approval_id: str
    node_id: str
    public_type: str
    request_contract: str | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class ResumeInput:
    """Application input used to resume an interrupted workflow."""

    approved: bool
    selected_outlier_id: str | None = None
    comment: str | None = None
    values: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NodeExecutionResult:
    """Result returned by one node executor."""

    state_update: Mapping[str, Any] = field(default_factory=dict)
    approval_request: ApprovalRequest | None = None


@dataclass(frozen=True)
class WorkflowExecutionResult:
    """Result returned by the workflow engine."""

    status: ExecutionStatus
    state: dict[str, Any]
    current_node: str | None
    approval_request: ApprovalRequest | None = None
    error: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.FAILED,
        }


class WorkflowExecutionError(RuntimeError):
    """Base error raised by the execution engine."""


class NodeExecutionError(WorkflowExecutionError):
    """Raised when a workflow node cannot be executed."""


class RoutingError(WorkflowExecutionError):
    """Raised when a workflow destination cannot be determined."""


class ApprovalResumeError(WorkflowExecutionError):
    """Raised when an approval workflow cannot be resumed."""


