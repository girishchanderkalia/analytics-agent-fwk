from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
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
    AgentRuntimeResumeRequest,
    AgentRuntimeStartRequest,
    AgentRuntimeStatus,
    CompiledGraphCache,
    GraphResumeUnavailableError,
    InvalidResumeRequestError,
    LangGraphAgentRuntime,
    build_resume_payload,
)


@dataclass(frozen=True)
class Normalized:
    agent_id: str = "agent"
    version: str = "1"


@dataclass(frozen=True)
class FakeInterrupt:
    value: object
    id: str


class InterruptGraph:
    def __init__(self):
        self.calls = []

    async def ainvoke(self, value, *, config):
        self.calls.append((value, config))
        if isinstance(value, ResumeCommand):
            return {"approved": value.resume}
        return {
            "question": value["question"],
            "__interrupt__": (
                FakeInterrupt(
                    value={"question": "Approve?"},
                    id="interrupt-1",
                ),
            ),
        }


@dataclass(frozen=True)
class ResumeCommand:
    resume: object


class Compiler:
    def __init__(self, graph):
        self.graph = graph

    def compile(self, normalized, *, checkpointer=None, store=None):
        return self.graph


def catalog():
    value = InMemoryAgentRegistrationCatalog()
    value.register_atomic((
        AgentRegistrationRecord(
            key=AgentRegistrationKey("app", "agent", "1"),
            definition_root=Path("package").resolve(),
            definition_fingerprint="fingerprint",
            registered_at=datetime.now(timezone.utc),
        ),
    ))
    return value


def runtime(*, checkpointer=object()):
    graph = InterruptGraph()
    value = LangGraphAgentRuntime(
        catalog(),
        lambda root: Normalized(),
        Compiler(graph),
        CompiledGraphCache(),
        checkpointer=checkpointer,
        command_factory=lambda resume, interrupt_id: ResumeCommand(
            build_resume_payload(resume, interrupt_id)
        ),
    )
    return value, graph


def test_start_surfaces_interrupt_payload_and_id() -> None:
    value, _ = runtime()
    result = asyncio.run(
        value.start(
            AgentRuntimeStartRequest(
                "app", "agent", "1", "thread-1", {"question": "Run"}
            )
        )
    )
    assert result.status is AgentRuntimeStatus.INTERRUPTED
    assert result.state == {"question": "Run"}
    assert result.interrupts[0].interrupt_id == "interrupt-1"
    assert result.interrupts[0].value == {"question": "Approve?"}


def test_resume_uses_same_thread_and_targeted_interrupt() -> None:
    value, graph = runtime()
    result = asyncio.run(
        value.resume(
            AgentRuntimeResumeRequest(
                "app",
                "agent",
                "1",
                "thread-1",
                True,
                interrupt_id="interrupt-1",
            )
        )
    )
    command, config = graph.calls[0]
    assert command.resume == {"interrupt-1": True}
    assert config == {"configurable": {"thread_id": "thread-1"}}
    assert result.status is AgentRuntimeStatus.COMPLETED
    assert result.state == {"approved": {"interrupt-1": True}}


def test_resume_next_interrupt_uses_scalar_value() -> None:
    value, graph = runtime()
    asyncio.run(
        value.resume(
            AgentRuntimeResumeRequest(
                "app", "agent", "1", "thread-1", "approved"
            )
        )
    )
    assert graph.calls[0][0].resume == "approved"


def test_resume_requires_checkpointer() -> None:
    value, _ = runtime(checkpointer=None)
    with pytest.raises(GraphResumeUnavailableError):
        asyncio.run(
            value.resume(
                AgentRuntimeResumeRequest(
                    "app", "agent", "1", "thread-1", True
                )
            )
        )


def test_none_resume_value_is_rejected() -> None:
    with pytest.raises(InvalidResumeRequestError):
        AgentRuntimeResumeRequest(
            "app", "agent", "1", "thread-1", None
        )
