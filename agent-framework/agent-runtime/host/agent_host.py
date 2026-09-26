"""Stable host interface for starting and resuming agent executions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from catalog.agent_catalog import AgentCatalog
from execution.execution_models import ResumeInput, WorkflowExecutionResult

from .runtime_composition import ComposedAgentRuntime, RuntimeComposer


class AgentHostError(ValueError):
    """Base error raised by the Agent Host."""


@dataclass(frozen=True)
class HostedExecutionResult:
    """Workflow result enriched with resolved agent identity."""

    agent_id: str
    agent_version: str
    result: WorkflowExecutionResult


class AgentHost:
    """Resolve agents, compose runtimes, and execute workflows."""

    def __init__(
        self,
        catalog: AgentCatalog,
        composer: RuntimeComposer,
        cache_runtimes: bool = True,
    ) -> None:
        self.catalog = catalog
        self.composer = composer
        self.cache_runtimes = cache_runtimes
        self._runtimes: dict[tuple[str, str], ComposedAgentRuntime] = {}

    def start(
        self,
        agent_id: str,
        initial_state: Mapping[str, Any] | None = None,
        version: str | None = None,
    ) -> HostedExecutionResult:
        """Start a new execution for a resolved agent version."""

        runtime = self.runtime(agent_id, version)
        result = runtime.workflow_engine.run(initial_state)
        return HostedExecutionResult(
            agent_id=runtime.entry.agent_id,
            agent_version=runtime.entry.version,
            result=result,
        )

    def resume(
        self,
        agent_id: str,
        state: Mapping[str, Any],
        current_node: str,
        resume_input: ResumeInput,
        version: str | None = None,
    ) -> HostedExecutionResult:
        """Resume an interrupted execution for a resolved agent version."""

        runtime = self.runtime(agent_id, version)
        result = runtime.workflow_engine.resume(
            state=state,
            current_node=current_node,
            resume_input=resume_input,
        )
        return HostedExecutionResult(
            agent_id=runtime.entry.agent_id,
            agent_version=runtime.entry.version,
            result=result,
        )

    def runtime(
        self,
        agent_id: str,
        version: str | None = None,
    ) -> ComposedAgentRuntime:
        """Resolve and compose an executable runtime."""

        entry = self.catalog.resolve(agent_id, version)
        key = (entry.agent_id, entry.version)

        if self.cache_runtimes and key in self._runtimes:
            return self._runtimes[key]

        runtime = self.composer.compose(entry)

        if self.cache_runtimes:
            self._runtimes[key] = runtime

        return runtime

    def clear_cache(self) -> None:
        """Remove all composed runtime instances from the host cache."""

        self._runtimes.clear()
