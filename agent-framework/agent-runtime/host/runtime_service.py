"""Application Agent Runtime orchestration service."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any, Protocol
from uuid import uuid4

from execution.execution_models import (
    ExecutionStatus,
    ResumeInput,
    WorkflowExecutionResult,
)
from persistence.conversation_store import ConversationStore
from persistence.persistence_models import (
    ConversationRecord,
    ConversationStatus,
)

from .runtime_models import (
    ChatCommand,
    ConversationStateError,
    ResumeCommand,
    RuntimeResponse,
)


class AgentRepositoryProtocol(Protocol):
    """Subset of AgentRepository used by the Runtime Service."""

    def load(self, agent_reference: str) -> Any:
        """Load one validated agent definition bundle."""
        ...

    def load_all(self) -> Mapping[str, Any]:
        """Load all bundles indexed by declared agent ID."""
        ...


class WorkflowEngineProtocol(Protocol):
    """Execution Engine behavior required by the Runtime Service."""

    def run(
        self,
        initial_state: Mapping[str, Any] | None = None,
    ) -> WorkflowExecutionResult:
        """Start a workflow."""
        ...

    def resume(
        self,
        *,
        state: Mapping[str, Any],
        current_node: str,
        resume_input: ResumeInput,
    ) -> WorkflowExecutionResult:
        """Resume a workflow."""
        ...


EngineFactory = Callable[[Any], WorkflowEngineProtocol]


class RuntimeService:
    """Coordinate definitions, execution, and conversation persistence."""

    def __init__(
        self,
        *,
        agent_repository: AgentRepositoryProtocol,
        conversation_store: ConversationStore,
        engine_factory: EngineFactory,
    ) -> None:
        self.agent_repository = agent_repository
        self.conversation_store = conversation_store
        self.engine_factory = engine_factory

    def start_chat(self, command: ChatCommand) -> RuntimeResponse:
        """Start, execute, and persist a new agent conversation."""

        command.validate()
        bundle = self._load_agent(command.agent_id)
        engine = self.engine_factory(bundle)
        conversation_id = str(uuid4())

        initial_state = self._build_initial_state(
            bundle=bundle,
            command=command,
            conversation_id=conversation_id,
        )

        execution_result = engine.run(initial_state)
        record = self.conversation_store.create(
            conversation_id=conversation_id,
            agent_id=_bundle_agent_id(bundle),
            state=execution_result.state,
            status=_conversation_status(execution_result.status),
            current_node=execution_result.current_node,
            pending_approval=_approval_as_dict(
                execution_result.approval_request
            ),
        )

        return self._to_response(record)

    def resume(self, command: ResumeCommand) -> RuntimeResponse:
        """Resume and persist a conversation waiting for approval."""

        command.validate()
        record = self.conversation_store.get(command.conversation_id)

        if record.status is not ConversationStatus.WAITING_FOR_APPROVAL:
            raise ConversationStateError(
                "Conversation is not waiting for approval: "
                f"{record.conversation_id}"
            )

        if not record.current_node:
            raise ConversationStateError(
                "Conversation has no resumable current node: "
                f"{record.conversation_id}"
            )

        if command.expected_version is not None:
            if command.expected_version != record.version:
                raise ConversationStateError(
                    "Conversation version does not match the "
                    "requested expected_version"
                )

        bundle = self._load_agent(record.agent_id)
        engine = self.engine_factory(bundle)

        execution_result = engine.resume(
            state=record.state,
            current_node=record.current_node,
            resume_input=ResumeInput(
                approved=command.approved,
                selected_outlier_id=command.selected_outlier_id,
                comment=command.comment,
                values=dict(command.values),
            ),
        )

        updated = self.conversation_store.update(
            conversation_id=record.conversation_id,
            expected_version=record.version,
            state=execution_result.state,
            status=_conversation_status(execution_result.status),
            current_node=execution_result.current_node,
            pending_approval=_approval_as_dict(
                execution_result.approval_request
            ),
        )

        return self._to_response(updated)

    def get_conversation(self, conversation_id: str) -> RuntimeResponse:
        """Return the public representation of a conversation."""

        record = self.conversation_store.get(conversation_id)
        return self._to_response(record)

    def _load_agent(self, agent_reference: str) -> Any:
        """Load an agent by directory name or declared agent ID."""

        try:
            return self.agent_repository.load(agent_reference)
        except Exception as direct_error:
            try:
                bundles = self.agent_repository.load_all()
            except Exception:
                raise direct_error

            bundle = bundles.get(agent_reference)
            if bundle is None:
                raise direct_error
            return bundle

    @staticmethod
    def _build_initial_state(
        *,
        bundle: Any,
        command: ChatCommand,
        conversation_id: str,
    ) -> dict[str, Any]:
        """Build only state fields declared by the selected agent."""

        declared_fields = bundle.state.metadata.get("fields", {})
        supplied: dict[str, Any] = {}

        candidates = {
            "conversation_id": conversation_id,
            "agent_id": _bundle_agent_id(bundle),
            "user_id": command.user_id,
            "question": command.message.strip(),
            "application_context": dict(command.application_context),
            "conversation_context": dict(command.application_context),
        }

        for field_name, value in candidates.items():
            if field_name in declared_fields:
                supplied[field_name] = deepcopy(value)

        return supplied

    @staticmethod
    def _to_response(record: ConversationRecord) -> RuntimeResponse:
        """Create a public response without runtime-internal identifiers."""

        public_result = _public_result(record.state)

        return RuntimeResponse(
            conversation_id=record.conversation_id,
            agent_id=record.agent_id,
            status=record.status.value,
            version=record.version,
            result=public_result,
            approval_request=(
                deepcopy(record.pending_approval)
                if record.pending_approval is not None
                else None
            ),
        )


def _bundle_agent_id(bundle: Any) -> str:
    if hasattr(bundle, "agent_id"):
        value = bundle.agent_id
    else:
        value = bundle.agent.metadata.get("id")

    if not isinstance(value, str) or not value:
        raise ConversationStateError(
            "Loaded agent bundle has no agent ID"
        )
    return value


def _conversation_status(status: ExecutionStatus) -> ConversationStatus:
    try:
        return ConversationStatus(status.value)
    except ValueError as exc:
        raise ConversationStateError(
            f"Unsupported execution status: {status!r}"
        ) from exc


def _approval_as_dict(approval: Any) -> dict[str, Any] | None:
    if approval is None:
        return None

    if isinstance(approval, Mapping):
        return deepcopy(dict(approval))

    return {
        "approval_id": approval.approval_id,
        "node_id": approval.node_id,
        "public_type": approval.public_type,
        "request_contract": approval.request_contract,
        "payload": deepcopy(approval.payload),
    }


def _public_result(state: Mapping[str, Any]) -> dict[str, Any]:
    """Return application-facing state while excluding runtime internals."""

    excluded = {
        "agent_id",
        "user_id",
        "messages",
        "capability_events",
        "error",
        "current_activity",
        "pending_approval",
        "pending_action",
        "registration_poll_count",
    }

    result = {
        key: deepcopy(value)
        for key, value in state.items()
        if key not in excluded
    }

    for forbidden in (
        "thread_id",
        "threadId",
        "session_id",
        "sessionId",
        "checkpoint_id",
        "checkpointId",
        "current_node",
        "currentNode",
    ):
        result.pop(forbidden, None)

    return result
