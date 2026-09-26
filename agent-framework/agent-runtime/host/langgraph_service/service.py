"""LangGraph-backed conversation Runtime Service."""
from __future__ import annotations
from typing import Any
from uuid import uuid4
from .cache import CompiledAgentCache, CompiledAgentCacheKey
from .commands import create_resume_command
from .errors import ConversationTransitionError
from .models import LangGraphChatCommand, LangGraphResumeCommand, LangGraphRuntimeResponse
from .result_mapper import LangGraphResultMapper
from .version_resolver import AgentVersionResolver

class LangGraphRuntimeService:
    def __init__(self, *, resolver: AgentVersionResolver, compiler: Any, dependency_factory: Any, checkpointer: Any, metadata_store: Any, cache: CompiledAgentCache | None = None, mapper: LangGraphResultMapper | None = None) -> None:
        self.resolver=resolver; self.compiler=compiler; self.dependency_factory=dependency_factory
        self.checkpointer=checkpointer; self.metadata_store=metadata_store
        self.cache=cache or CompiledAgentCache(); self.mapper=mapper or LangGraphResultMapper()

    def start_chat(self, command: LangGraphChatCommand) -> LangGraphRuntimeResponse:
        if not isinstance(command.message, str) or not command.message.strip():
            raise ConversationTransitionError("message must be a non-empty string")
        reference=self.resolver.resolve(agent_id=command.agent_id,requested_version=command.agent_version)
        agent=self._compiled(reference)
        conversation_id=str(uuid4())
        state={
            "conversation_id": conversation_id,
            "question": command.message.strip(),
            "user_id": command.user_id,
            "application_context": dict(command.application_context),
            "status": "running",
        }
        raw=agent.invoke(conversation_id=conversation_id,state=state)
        status,result,approval=self.mapper.map(raw)
        record=self.metadata_store.create(
            conversation_id=conversation_id,
            agent_id=reference.agent_id,
            agent_version=reference.version,
            definition_digest=reference.definition_digest,
            status=status,
            public_result=result,
            pending_approval=approval,
        )
        return self._response(record,result,approval)

    def resume(self, command: LangGraphResumeCommand) -> LangGraphRuntimeResponse:
        record=self.metadata_store.get(command.conversation_id)
        if record.status != "waiting_for_approval":
            raise ConversationTransitionError("Conversation is not waiting for approval")
        if command.expected_version is not None and record.version != command.expected_version:
            raise ConversationTransitionError("Conversation version conflict")
        reference=self.resolver.resolve(agent_id=record.agent_id,requested_version=record.agent_version)
        if reference.definition_digest != record.definition_digest:
            raise ConversationTransitionError("Persisted agent definition digest does not match repository")
        agent=self._compiled(reference)
        raw=agent.resume(
            conversation_id=record.conversation_id,
            command=create_resume_command(
                approved=command.approved,
                selected_outlier_id=command.selected_outlier_id,
                comment=command.comment,
                values=command.values,
            ),
        )
        status,result,approval=self.mapper.map(raw)
        updated=self.metadata_store.update(
            conversation_id=record.conversation_id,
            expected_version=record.version,
            status=status,
            public_result=result,
            pending_approval=approval,
        )
        return self._response(updated,result,approval)

    def _compiled(self, reference):
        key=CompiledAgentCacheKey(reference.agent_id,reference.version,reference.definition_digest)
        return self.cache.get_or_create(
            key,
            lambda: self.compiler.compile(
                definition=reference.definition,
                dependencies=self.dependency_factory.create(reference.definition),
                checkpointer=self.checkpointer,
            ),
        )

    @staticmethod
    def _response(record, result, approval):
        return LangGraphRuntimeResponse(
            conversation_id=record.conversation_id,
            agent_id=record.agent_id,
            agent_version=record.agent_version,
            status=record.status,
            version=record.version,
            result=result,
            approval_request=approval,
        )
