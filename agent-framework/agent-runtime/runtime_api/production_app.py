"""Production application builder using the fixed framework context."""

from __future__ import annotations

from execution.execution_context import ExecutionContext

from .app import create_app
from .production_composition import create_production_runtime_service
from .settings import RuntimeSettings


def create_production_app(
    execution_context: ExecutionContext,
    settings: RuntimeSettings | None = None,
):
    """Build the production API from the framework's fixed dependencies."""

    runtime_service = create_production_runtime_service(
        execution_context=execution_context,
        settings=settings,
    )

    return create_app(runtime_service=runtime_service)
