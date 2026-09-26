"""Production composition around the framework's fixed ExecutionContext."""

from __future__ import annotations

from execution.execution_context import ExecutionContext
from host.runtime_composition import (
    RuntimeDependencies,
    create_runtime_service,
)

from .production_policy import DEFAULT_MAXIMUM_WORKFLOW_STEPS
from .settings import RuntimeSettings, repository_root


def create_production_runtime_service(
    execution_context: ExecutionContext,
    settings: RuntimeSettings | None = None,
):
    """Create the persisted Runtime Service using fixed framework components.

    The framework bootstrap owns construction of the fixed model gateway,
    capability dispatcher, operation registry, and contract provider. This
    function adds production persistence and workflow policy around that
    already composed ExecutionContext.
    """

    effective_settings = settings or RuntimeSettings()

    return create_runtime_service(
        repository_root=repository_root(),
        database_path=effective_settings.resolved_database_path(),
        dependencies=RuntimeDependencies(
            execution_context=execution_context
        ),
        maximum_steps=DEFAULT_MAXIMUM_WORKFLOW_STEPS,
    )
