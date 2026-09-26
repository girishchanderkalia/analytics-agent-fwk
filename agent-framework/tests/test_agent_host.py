"""Tests for the stable Agent Host interface."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

V3_ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"
AGENT_REPOSITORY_ROOT = V3_ROOT / "agents"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))

from catalog import AgentCatalog  # noqa: E402
from execution.definition_loader import AgentRepository  # noqa: E402
from execution.execution_models import (  # noqa: E402
    ExecutionStatus,
    ResumeInput,
    WorkflowExecutionResult,
)
from host import AgentHost, ComposedAgentRuntime  # noqa: E402


class FakeEngine:
    def __init__(self) -> None:
        self.started_with: Any = None
        self.resumed_with: Any = None

    def run(self, initial_state: Any) -> WorkflowExecutionResult:
        self.started_with = initial_state
        return WorkflowExecutionResult(
            status=ExecutionStatus.COMPLETED,
            state={"status": "completed"},
            current_node=None,
        )

    def resume(
        self,
        state: Any,
        current_node: str,
        resume_input: ResumeInput,
    ) -> WorkflowExecutionResult:
        self.resumed_with = (state, current_node, resume_input)
        return WorkflowExecutionResult(
            status=ExecutionStatus.COMPLETED,
            state={"status": "completed"},
            current_node=None,
        )


class FakeComposer:
    def __init__(self) -> None:
        self.count = 0
        self.engine = FakeEngine()

    def compose(self, entry: Any) -> ComposedAgentRuntime:
        self.count += 1
        return ComposedAgentRuntime(
            entry=entry,
            contract_provider=object(),
            operation_registry=object(),
            capability_dispatcher=object(),
            execution_context=object(),
            workflow_engine=self.engine,
        )


def create_host() -> tuple[AgentHost, FakeComposer]:
    catalog = AgentCatalog(AgentRepository(AGENT_REPOSITORY_ROOT))
    composer = FakeComposer()
    return AgentHost(catalog, composer), composer


def test_host_starts_agent() -> None:
    host, composer = create_host()
    hosted = host.start(
        "opo-monitoring-agent",
        {"question": "Show trends"},
    )
    assert hosted.agent_id == "opo-monitoring-agent"
    assert hosted.agent_version == "1.0"
    assert hosted.result.status is ExecutionStatus.COMPLETED
    assert composer.engine.started_with == {"question": "Show trends"}


def test_host_resumes_agent() -> None:
    host, composer = create_host()
    resume_input = ResumeInput(approved=True)
    hosted = host.resume(
        "opo-monitoring-agent",
        {"status": "waiting_for_approval"},
        "approve_investigation",
        resume_input,
    )
    assert hosted.result.status is ExecutionStatus.COMPLETED
    assert composer.engine.resumed_with == (
        {"status": "waiting_for_approval"},
        "approve_investigation",
        resume_input,
    )


def test_host_caches_runtime() -> None:
    host, composer = create_host()
    first = host.runtime("opo-monitoring-agent")
    second = host.runtime("opo-monitoring-agent")
    assert first is second
    assert composer.count == 1


def test_host_can_clear_runtime_cache() -> None:
    host, composer = create_host()
    first = host.runtime("opo-monitoring-agent")
    host.clear_cache()
    second = host.runtime("opo-monitoring-agent")
    assert first is not second
    assert composer.count == 2
