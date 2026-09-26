"""Fixed framework bootstrap for model, capability, and operation execution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from execution.execution_context import ExecutionContext
from runtime_api import RuntimeSettings, create_production_app

from .capability_dispatcher_adapter import (
    CapabilityRegistryProtocol,
    create_capability_dispatcher,
)
from .model_gateway_adapter import create_model_gateway
from .operation_registry_bootstrap import (
    OperationHandler,
    create_operation_registry,
)


def create_execution_context(
    capability_registry: CapabilityRegistryProtocol,
    operations: Mapping[str, OperationHandler],
    contract_provider: Any,
    permissions: frozenset[str] | None = None,
    approved_capabilities: frozenset[str] | None = None,
) -> ExecutionContext:
    """Compose fixed model, capability, and operation infrastructure."""

    return ExecutionContext(
        model_gateway=create_model_gateway(),
        capability_dispatcher=create_capability_dispatcher(
            capability_registry
        ),
        operation_registry=create_operation_registry(operations),
        contract_provider=contract_provider,
        permissions=permissions or frozenset(),
        approved_capabilities=(
            approved_capabilities or frozenset()
        ),
    )


def create_application(
    capability_registry: CapabilityRegistryProtocol,
    operations: Mapping[str, OperationHandler],
    contract_provider: Any,
    permissions: frozenset[str] | None = None,
    approved_capabilities: frozenset[str] | None = None,
    settings: RuntimeSettings | None = None,
):
    """Create the persisted API from fixed framework components."""

    context = create_execution_context(
        capability_registry=capability_registry,
        operations=operations,
        contract_provider=contract_provider,
        permissions=permissions,
        approved_capabilities=approved_capabilities,
    )

    return create_production_app(
        execution_context=context,
        settings=settings,
    )
