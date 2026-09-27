"""Serve the persisted conversation API from the LangGraph runtime.

The routes are synchronous and identify a conversation only by ID, so this
service resolves the registered agent and keeps the public conversation
metadata; graph state itself stays in LangGraph's checkpointer.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any
from uuid import uuid4

from host.runtime_models import (
    ChatCommand,
    ConversationStateError,
    ResumeCommand,
    RuntimeResponse,
)
from runtime_service_langgraph import (
    RuntimeServiceResumeRequest,
    RuntimeServiceStartRequest,
)

WAITING = "waiting_for_approval"
COMPLETED = "completed"


class _GraphLoop:
    """One long-lived event loop shared by every request.

    Model and MCP clients cache connections against the loop that created
    them, so a loop per request closes those connections underneath them.
    """

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever,
            name="langgraph-runtime",
            daemon=True,
        )
        self._thread.start()

    def run(self, awaitable: Any) -> Any:
        return asyncio.run_coroutine_threadsafe(awaitable, self._loop).result()


class LangGraphConversationService:
    """Adapt the LangGraph runtime to the application-facing chat API."""

    def __init__(
        self,
        *,
        runtime_service: Any,
        catalog: Any,
        metadata_store: Any,
        normalizer: Any,
    ) -> None:
        self.runtime_service = runtime_service
        self.catalog = catalog
        self.metadata_store = metadata_store
        self.normalizer = normalizer
        self._loop = _GraphLoop()

    def start_chat(self, command: ChatCommand) -> RuntimeResponse:
        command.validate()
        record = self._registration(command)
        conversation_id = str(uuid4())

        result = self._loop.run(
            self.runtime_service.start(
                RuntimeServiceStartRequest(
                    application_id=record.key.application_id,
                    agent_id=record.key.agent_id,
                    version=record.key.version,
                    conversation_id=conversation_id,
                    initial_state=self._initial_state(
                        record,
                        command,
                        conversation_id,
                    ),
                )
            )
        )

        status, approval = _status(result)
        metadata = self.metadata_store.create(
            conversation_id=conversation_id,
            application_id=record.key.application_id,
            agent_id=record.key.agent_id,
            agent_version=record.key.version,
            definition_digest=record.definition_fingerprint,
            status=status,
            public_result=dict(result.state),
            pending_approval=approval,
        )
        return _response(metadata)

    def resume(self, command: ResumeCommand) -> RuntimeResponse:
        command.validate()
        metadata = self._metadata(command.conversation_id)

        if metadata.status != WAITING:
            raise ConversationStateError(
                "Conversation is not waiting for approval: "
                f"{command.conversation_id}"
            )
        if (
            command.expected_version is not None
            and command.expected_version != metadata.version
        ):
            raise ConversationStateError(
                "Conversation version does not match the requested "
                "expected_version"
            )

        pending = metadata.pending_approval or {}
        result = self._loop.run(
            self.runtime_service.resume(
                RuntimeServiceResumeRequest(
                    application_id=metadata.application_id,
                    agent_id=metadata.agent_id,
                    version=metadata.agent_version,
                    conversation_id=command.conversation_id,
                    resume_value=_decision(command),
                    interrupt_id=pending.get("interrupt_id"),
                )
            )
        )

        status, approval = _status(result)
        updated = self.metadata_store.update(
            conversation_id=command.conversation_id,
            expected_version=metadata.version,
            status=status,
            public_result=dict(result.state),
            pending_approval=approval,
        )
        return _response(updated)

    def get_conversation(self, conversation_id: str) -> RuntimeResponse:
        return _response(self._metadata(conversation_id))

    def _initial_state(
        self,
        record: Any,
        command: ChatCommand,
        conversation_id: str,
    ) -> dict[str, Any]:
        """Seed every declared field so state references resolve from the start."""

        definition = self.normalizer(record.definition_root)
        properties = definition.state.schema.get("properties", {})
        state = {
            name: schema.get("default")
            for name, schema in properties.items()
        }
        state.update(
            {
                "conversation_id": conversation_id,
                "question": command.message.strip(),
                "user_id": command.user_id,
                "conversation_context": dict(command.application_context),
            }
        )
        return {key: value for key, value in state.items() if key in properties}

    def _registration(self, command: ChatCommand) -> Any:
        if not command.application_id:
            raise ConversationStateError(
                "application_id is required to resolve a registered agent"
            )
        try:
            return self.catalog.resolve(
                command.application_id,
                command.agent_id,
                command.agent_version,
            )
        except KeyError as exc:
            raise ConversationStateError(
                f"Agent is not registered: {command.application_id}/"
                f"{command.agent_id}"
            ) from exc

    def _metadata(self, conversation_id: str) -> Any:
        try:
            return self.metadata_store.get(conversation_id)
        except KeyError as exc:
            raise ConversationStateError(
                f"Conversation not found: {conversation_id}"
            ) from exc


def _decision(command: ResumeCommand) -> dict[str, Any]:
    """Pass the analyst decision through as the interrupt's resume value."""

    decision: dict[str, Any] = {"approved": command.approved}
    if command.selected_outlier_id is not None:
        decision["selected_outlier_id"] = command.selected_outlier_id
    if command.comment is not None:
        decision["comment"] = command.comment
    decision.update(dict(command.values))
    return decision


def _status(result: Any) -> tuple[str, dict[str, Any] | None]:
    interrupts = getattr(result, "interrupts", ())
    if not interrupts:
        return COMPLETED, None

    interrupt = interrupts[0]
    value = interrupt.value if isinstance(interrupt.value, dict) else {
        "value": interrupt.value
    }
    return WAITING, {"interrupt_id": interrupt.interrupt_id, **value}


def _response(metadata: Any) -> RuntimeResponse:
    return RuntimeResponse(
        conversation_id=metadata.conversation_id,
        agent_id=metadata.agent_id,
        agent_version=metadata.agent_version,
        status=metadata.status,
        version=metadata.version,
        result=dict(metadata.public_result),
        approval_request=(
            dict(metadata.pending_approval)
            if metadata.pending_approval is not None
            else None
        ),
    )
