"""Runtime Service facade routed exclusively through LangGraphAgentRuntime."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from langgraph_runtime.runtime_api import (
    AgentRuntimeResumeRequest,
    AgentRuntimeStartRequest,
    AgentRuntimeStateRequest,
)

from .errors import RuntimeServiceExecutionError
from .models import (
    RuntimeInterrupt,
    RuntimeServiceResult,
    RuntimeServiceResumeRequest,
    RuntimeServiceStartRequest,
    RuntimeServiceStateRequest,
)


class LangGraphRuntimeService:
    """Stable service boundary over the central LangGraph runtime.

    The conversation ID maps directly to LangGraph's thread ID. This service
    contains no workflow traversal, routing, checkpoint bookkeeping, or
    application-specific behavior.
    """

    def __init__(self, agent_runtime: Any) -> None:
        self.agent_runtime = agent_runtime

    async def start(
        self,
        request: RuntimeServiceStartRequest,
    ) -> RuntimeServiceResult:
        try:
            result = await self.agent_runtime.start(
                AgentRuntimeStartRequest(
                    application_id=request.application_id,
                    agent_id=request.agent_id,
                    version=request.version,
                    thread_id=request.conversation_id,
                    initial_state=request.initial_state,
                )
            )
        except Exception as exc:
            raise RuntimeServiceExecutionError(
                "Could not start registered agent execution"
            ) from exc
        return _map_result(result)

    async def resume(
        self,
        request: RuntimeServiceResumeRequest,
    ) -> RuntimeServiceResult:
        try:
            result = await self.agent_runtime.resume(
                AgentRuntimeResumeRequest(
                    application_id=request.application_id,
                    agent_id=request.agent_id,
                    version=request.version,
                    thread_id=request.conversation_id,
                    resume_value=request.resume_value,
                    interrupt_id=request.interrupt_id,
                )
            )
        except Exception as exc:
            raise RuntimeServiceExecutionError(
                "Could not resume registered agent execution"
            ) from exc
        return _map_result(result)

    async def get_state(
        self,
        request: RuntimeServiceStateRequest,
    ) -> Mapping[str, Any]:
        try:
            state = await self.agent_runtime.get_state(
                AgentRuntimeStateRequest(
                    application_id=request.application_id,
                    agent_id=request.agent_id,
                    version=request.version,
                    thread_id=request.conversation_id,
                )
            )
        except Exception as exc:
            raise RuntimeServiceExecutionError(
                "Could not retrieve registered agent state"
            ) from exc
        if not isinstance(state, Mapping):
            raise RuntimeServiceExecutionError(
                "Central runtime state must be a mapping"
            )
        return deepcopy(dict(state))


def _map_result(result: Any) -> RuntimeServiceResult:
    return RuntimeServiceResult(
        application_id=result.application_id,
        agent_id=result.agent_id,
        version=result.version,
        conversation_id=result.thread_id,
        status=result.status.value,
        state=deepcopy(dict(result.state)),
        interrupts=tuple(
            RuntimeInterrupt(
                interrupt_id=interrupt.interrupt_id,
                value=deepcopy(interrupt.value),
            )
            for interrupt in result.interrupts
        ),
    )
