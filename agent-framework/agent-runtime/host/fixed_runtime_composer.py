"""Final per-agent runtime composer for fixed framework dependencies."""
from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from bootstrap.capability_dispatcher_adapter import CapabilityRegistryProtocol
from bootstrap.operation_registry_bootstrap import OperationHandler
from execution.workflow_engine import WorkflowEngine
from .runtime_context_factory import ExecutionSecurityContext, RuntimeContextFactory

@dataclass(frozen=True)
class ComposedAgentExecution:
    """Executable objects composed for one resolved agent bundle."""
    bundle: Any
    context: Any
    engine: WorkflowEngine

class FixedRuntimeComposer:
    """Compose Workflow Engines after agent resolution."""
    def __init__(
        self,
        capability_registry: CapabilityRegistryProtocol,
        operations: Mapping[str, OperationHandler],
        security_context: ExecutionSecurityContext | None = None,
        maximum_steps: int = 100,
        context_factory: RuntimeContextFactory | None = None,
    ) -> None:
        if maximum_steps <= 0:
            raise ValueError("maximum_steps must be greater than zero")
        self.maximum_steps = maximum_steps
        self.context_factory = context_factory or RuntimeContextFactory(
            capability_registry=capability_registry,
            operations=operations,
            security_context=security_context,
        )

    def compose(self, bundle: Any) -> ComposedAgentExecution:
        context = self.context_factory.create(bundle)
        engine = WorkflowEngine(bundle=bundle, context=context, maximum_steps=self.maximum_steps)
        return ComposedAgentExecution(bundle=bundle, context=context, engine=engine)
