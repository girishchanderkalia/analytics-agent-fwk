from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent-framework" / "agent-runtime"))

from runtime_service_langgraph import (
    LangGraphRuntimeService,
    RuntimeServiceResumeRequest,
    RuntimeServiceStartRequest,
    RuntimeServiceStateRequest,
)
from runtime_service_langgraph.errors import RuntimeServiceExecutionError


class Status(StrEnum):
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class Interrupt:
    interrupt_id: str
    value: object


@dataclass(frozen=True)
class Result:
    application_id: str
    agent_id: str
    version: str
    thread_id: str
    status: Status
    state: dict
    interrupts: tuple = ()


class AgentRuntime:
    def __init__(self):
        self.start_request = None
        self.resume_request = None
        self.state_request = None

    async def start(self, request):
        self.start_request = request
        return Result(
            request.application_id,
            request.agent_id,
            request.version,
            request.thread_id,
            Status.INTERRUPTED,
            {"question": "Run"},
            (Interrupt("interrupt-1", {"question": "Approve?"}),),
        )

    async def resume(self, request):
        self.resume_request = request
        return Result(
            request.application_id,
            request.agent_id,
            request.version,
            request.thread_id,
            Status.COMPLETED,
            {"approved": request.resume_value},
        )

    async def get_state(self, request):
        self.state_request = request
        return {"thread": request.thread_id}


def test_start_maps_conversation_to_thread_and_interrupts() -> None:
    runtime = AgentRuntime()
    service = LangGraphRuntimeService(runtime)
    result = asyncio.run(
        service.start(
            RuntimeServiceStartRequest(
                "app", "agent", "1", "conversation-1", {"question": "Run"}
            )
        )
    )
    assert runtime.start_request.thread_id == "conversation-1"
    assert result.conversation_id == "conversation-1"
    assert result.status == "interrupted"
    assert result.interrupts[0].interrupt_id == "interrupt-1"


def test_resume_maps_service_request_to_runtime() -> None:
    runtime = AgentRuntime()
    service = LangGraphRuntimeService(runtime)
    result = asyncio.run(
        service.resume(
            RuntimeServiceResumeRequest(
                "app", "agent", "1", "conversation-1", True, "interrupt-1"
            )
        )
    )
    assert runtime.resume_request.thread_id == "conversation-1"
    assert runtime.resume_request.interrupt_id == "interrupt-1"
    assert result.state == {"approved": True}


def test_get_state_maps_conversation_to_thread() -> None:
    runtime = AgentRuntime()
    service = LangGraphRuntimeService(runtime)
    result = asyncio.run(
        service.get_state(
            RuntimeServiceStateRequest(
                "app", "agent", "1", "conversation-9"
            )
        )
    )
    assert result == {"thread": "conversation-9"}


def test_runtime_failures_are_mapped() -> None:
    class FailingRuntime:
        async def start(self, request):
            raise ValueError("failure")
    with pytest.raises(RuntimeServiceExecutionError):
        asyncio.run(
            LangGraphRuntimeService(FailingRuntime()).start(
                RuntimeServiceStartRequest(
                    "app", "agent", "1", "conversation", {}
                )
            )
        )
