"""Production composition for the fixed persisted Agent Runtime."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from bootstrap.capability_dispatcher_adapter import (
    CapabilityRegistryProtocol,
)
from bootstrap.operation_registry_bootstrap import (
    OperationHandler,
)
from execution.definition_loader import (
    AgentRepository,
)
from execution.workflow_engine import (
    WorkflowEngine,
)
from persistence.sqlite_conversation_store import (
    SQLiteConversationStore,
)

from .runtime_context_factory import (
    RuntimeContextFactory,
)
from .runtime_service import (
    RuntimeService,
)


def create_production_runtime_service(
    *,
    repository_root: Path | str,
    database_path: Path | str,
    capability_registry: CapabilityRegistryProtocol,
    operations: Mapping[str, OperationHandler],
    permissions: frozenset[str] | None = None,
    approved_capabilities: frozenset[str] | None = None,
    maximum_steps: int = 100,
) -> RuntimeService:
    """Create the fixed persisted Runtime Service."""

    if maximum_steps <= 0:
        raise ValueError(
            "maximum_steps must be greater than zero"
        )

    root = (
        Path(repository_root)
        .expanduser()
        .resolve()
    )

    agent_repository = AgentRepository(
        root / "agents"
    )

    conversation_store = (
        SQLiteConversationStore(
            database_path
        )
    )

    context_factory = RuntimeContextFactory(
        capability_registry=(
            capability_registry
        ),
        operations=operations,
        permissions=(
            permissions
            if permissions is not None
            else frozenset()
        ),
        approved_capabilities=(
            approved_capabilities
            if approved_capabilities is not None
            else frozenset()
        ),
    )

    def engine_factory(
        bundle: object,
    ) -> WorkflowEngine:
        execution_context = (
            context_factory.create(bundle)
        )

        return WorkflowEngine(
            bundle=bundle,
            context=execution_context,
            maximum_steps=maximum_steps,
        )

    return RuntimeService(
        agent_repository=agent_repository,
        conversation_store=conversation_store,
        engine_factory=engine_factory,
    )