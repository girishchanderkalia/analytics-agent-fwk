"""Central LangGraph runtime with interrupt and resume support."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from agent_registration import AgentRegistrationKey

from .graph_cache import CompiledGraphCache
from .interrupts import create_langgraph_command, extract_interrupts
from .runtime_errors import (
    GraphCompilationError,
    GraphInvocationError,
    GraphResumeUnavailableError,
    GraphStateUnavailableError,
    RegisteredAgentIdentityError,
    RegisteredAgentNotFoundError,
)
from .runtime_models import (
    AgentRuntimeResult,
    AgentRuntimeResumeRequest,
    AgentRuntimeStartRequest,
    AgentRuntimeStateRequest,
    AgentRuntimeStatus,
    CompiledGraphKey,
)


class LangGraphAgentRuntime:
    """Resolve, compile, invoke, interrupt, and resume registered agents."""

    def __init__(
        self,
        registration_catalog: Any,
        normalizer: Any,
        compiler: Any,
        graph_cache: CompiledGraphCache,
        *,
        checkpointer: Any = None,
        store: Any = None,
        command_factory: Any = create_langgraph_command,
    ) -> None:
        self.registration_catalog = registration_catalog
        self.normalizer = normalizer
        self.compiler = compiler
        self.graph_cache = graph_cache
        self.checkpointer = checkpointer
        self.store = store
        self.command_factory = command_factory

    async def start(
        self,
        request: AgentRuntimeStartRequest,
    ) -> AgentRuntimeResult:
        record = self._resolve_registration(
            request.application_id,
            request.agent_id,
            request.version,
        )
        graph = self._resolve_graph(record)
        output = await self._invoke_graph(
            graph,
            deepcopy(dict(request.initial_state)),
            request,
            operation="start",
        )
        return _result_from_output(request, output)

    async def resume(
        self,
        request: AgentRuntimeResumeRequest,
    ) -> AgentRuntimeResult:
        if self.checkpointer is None:
            raise GraphResumeUnavailableError(
                "LangGraph resume requires a configured checkpointer"
            )

        record = self._resolve_registration(
            request.application_id,
            request.agent_id,
            request.version,
        )
        graph = self._resolve_graph(record)
        command = self.command_factory(
            request.resume_value,
            request.interrupt_id,
        )
        output = await self._invoke_graph(
            graph,
            command,
            request,
            operation="resume",
        )
        return _result_from_output(request, output)

    async def get_state(
        self,
        request: AgentRuntimeStateRequest,
    ) -> Mapping[str, Any]:
        record = self._resolve_registration(
            request.application_id,
            request.agent_id,
            request.version,
        )
        graph = self._resolve_graph(record)
        state_method = getattr(graph, "aget_state", None)
        if state_method is None:
            raise GraphStateUnavailableError(
                "Compiled graph does not support asynchronous state retrieval"
            )
        try:
            snapshot = await _maybe_await(
                state_method(_thread_config(request.thread_id))
            )
        except Exception as exc:
            raise GraphStateUnavailableError(
                f"Graph state is unavailable for thread {request.thread_id!r}"
            ) from exc
        values = getattr(snapshot, "values", snapshot)
        if not isinstance(values, Mapping):
            raise GraphStateUnavailableError(
                "Graph state snapshot does not contain mapping values"
            )
        return deepcopy(dict(values))

    def invalidate(
        self,
        application_id: str,
        agent_id: str,
        version: str,
    ) -> int:
        return self.graph_cache.invalidate_agent(
            application_id,
            agent_id,
            version,
        )

    async def _invoke_graph(
        self,
        graph: Any,
        input_value: Any,
        request: Any,
        *,
        operation: str,
    ) -> Mapping[str, Any]:
        try:
            output = await _invoke(
                graph,
                input_value,
                _thread_config(request.thread_id),
            )
        except Exception as exc:
            if isinstance(exc, GraphInvocationError):
                raise
            raise GraphInvocationError(
                f"LangGraph {operation} failed for "
                f"{request.application_id}/{request.agent_id}/{request.version}"
            ) from exc
        if not isinstance(output, Mapping):
            raise GraphInvocationError(
                f"LangGraph {operation} must return a mapping"
            )
        return output

    def _resolve_registration(self, application_id, agent_id, version):
        key = AgentRegistrationKey(application_id, agent_id, version)
        try:
            return self.registration_catalog.get(key)
        except KeyError as exc:
            raise RegisteredAgentNotFoundError(
                f"Registered agent was not found: "
                f"{application_id}/{agent_id}/{version}"
            ) from exc

    def _resolve_graph(self, record: Any) -> Any:
        cache_key = CompiledGraphKey(
            application_id=record.key.application_id,
            agent_id=record.key.agent_id,
            version=record.key.version,
            definition_fingerprint=record.definition_fingerprint,
        )

        def compile_graph() -> Any:
            try:
                normalized = self.normalizer(record.definition_root)
            except Exception as exc:
                raise GraphCompilationError(
                    "Registered agent package normalization failed"
                ) from exc
            if (
                normalized.agent_id != record.key.agent_id
                or normalized.version != record.key.version
            ):
                raise RegisteredAgentIdentityError(
                    "Normalized package identity does not match registration"
                )
            try:
                return self.compiler.compile(
                    normalized,
                    checkpointer=self.checkpointer,
                    store=self.store,
                )
            except Exception as exc:
                raise GraphCompilationError(
                    "Registered agent graph compilation failed"
                ) from exc

        return self.graph_cache.get_or_create(cache_key, compile_graph)


async def _invoke(graph: Any, input_value: Any, config: Mapping[str, Any]) -> Any:
    async_method = getattr(graph, "ainvoke", None)
    if async_method is not None:
        return await _maybe_await(async_method(input_value, config=config))
    sync_method = getattr(graph, "invoke", None)
    if sync_method is None:
        raise GraphInvocationError(
            "Compiled graph exposes neither ainvoke nor invoke"
        )
    return sync_method(input_value, config=config)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _thread_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def _result_from_output(request: Any, output: Mapping[str, Any]) -> AgentRuntimeResult:
    interrupts = extract_interrupts(output)
    state = {
        key: deepcopy(value)
        for key, value in output.items()
        if key != "__interrupt__"
    }
    return AgentRuntimeResult(
        application_id=request.application_id,
        agent_id=request.agent_id,
        version=request.version,
        thread_id=request.thread_id,
        state=state,
        status=(
            AgentRuntimeStatus.INTERRUPTED
            if interrupts
            else AgentRuntimeStatus.COMPLETED
        ),
        interrupts=interrupts,
    )
