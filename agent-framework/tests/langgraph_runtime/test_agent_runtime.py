from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent-framework" / "agent-runtime"))

from agent_registration import (
    AgentRegistrationKey,
    AgentRegistrationRecord,
    InMemoryAgentRegistrationCatalog,
)
from langgraph_runtime.runtime_api import (
    AgentRuntimeStartRequest,
    AgentRuntimeStateRequest,
    CompiledGraphCache,
    GraphCompilationError,
    GraphInvocationError,
    GraphStateUnavailableError,
    LangGraphAgentRuntime,
    RegisteredAgentIdentityError,
    RegisteredAgentNotFoundError,
)


@dataclass(frozen=True)
class Normalized:
    agent_id: str = "agent"
    version: str = "1"


class Graph:
    def __init__(self):
        self.calls = []
    async def ainvoke(self, state, *, config):
        self.calls.append((state, config))
        return {**state, "completed": True}
    async def aget_state(self, config):
        return type("Snapshot", (), {"values": {"thread": config["configurable"]["thread_id"]}})()


class Compiler:
    def __init__(self, graph=None, failure=None):
        self.graph = graph or Graph()
        self.failure = failure
        self.calls = 0
    def compile(self, normalized, *, checkpointer=None, store=None):
        self.calls += 1
        if self.failure:
            raise self.failure
        return self.graph


def catalog():
    value = InMemoryAgentRegistrationCatalog()
    record = AgentRegistrationRecord(
        key=AgentRegistrationKey("app", "agent", "1"),
        definition_root=Path("package").resolve(),
        definition_fingerprint="fingerprint",
        registered_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    value.register_atomic((record,))
    return value


def runtime(normalizer=lambda root: Normalized(), compiler=None):
    return LangGraphAgentRuntime(
        catalog(),
        normalizer,
        compiler or Compiler(),
        CompiledGraphCache(),
    )


def start_request():
    return AgentRuntimeStartRequest(
        "app",
        "agent",
        "1",
        "thread-1",
        {"question": "Hello", "domain_field": 42},
    )


def test_start_invokes_graph_and_preserves_application_fields() -> None:
    compiler = Compiler()
    result = asyncio.run(runtime(compiler=compiler).start(start_request()))
    assert result.state == {
        "question": "Hello",
        "domain_field": 42,
        "completed": True,
    }
    assert compiler.graph.calls[0][1] == {
        "configurable": {"thread_id": "thread-1"}
    }


def test_second_start_reuses_compiled_graph() -> None:
    compiler = Compiler()
    agent_runtime = runtime(compiler=compiler)
    asyncio.run(agent_runtime.start(start_request()))
    asyncio.run(agent_runtime.start(start_request()))
    assert compiler.calls == 1


def test_missing_registration_is_rejected() -> None:
    agent_runtime = LangGraphAgentRuntime(
        InMemoryAgentRegistrationCatalog(),
        lambda root: Normalized(),
        Compiler(),
        CompiledGraphCache(),
    )
    with pytest.raises(RegisteredAgentNotFoundError):
        asyncio.run(agent_runtime.start(start_request()))


def test_package_identity_mismatch_is_rejected() -> None:
    with pytest.raises(RegisteredAgentIdentityError):
        asyncio.run(
            runtime(
                normalizer=lambda root: Normalized(agent_id="other")
            ).start(start_request())
        )


def test_normalization_and_compilation_failures_are_mapped() -> None:
    def fail_normalization(root):
        raise ValueError("bad package")
    with pytest.raises(GraphCompilationError):
        asyncio.run(runtime(normalizer=fail_normalization).start(start_request()))
    with pytest.raises(GraphCompilationError):
        asyncio.run(
            runtime(compiler=Compiler(failure=ValueError("bad graph"))).start(
                start_request()
            )
        )


def test_non_mapping_graph_result_is_rejected() -> None:
    class InvalidGraph:
        async def ainvoke(self, state, *, config):
            return "invalid"
    with pytest.raises(GraphInvocationError):
        asyncio.run(runtime(compiler=Compiler(graph=InvalidGraph())).start(start_request()))


def test_get_state_uses_thread_id() -> None:
    result = asyncio.run(
        runtime().get_state(
            AgentRuntimeStateRequest("app", "agent", "1", "thread-9")
        )
    )
    assert result == {"thread": "thread-9"}


def test_unavailable_state_is_reported() -> None:
    class NoStateGraph:
        async def ainvoke(self, state, *, config):
            return state
    with pytest.raises(GraphStateUnavailableError):
        asyncio.run(
            runtime(compiler=Compiler(graph=NoStateGraph())).get_state(
                AgentRuntimeStateRequest("app", "agent", "1", "thread")
            )
        )
