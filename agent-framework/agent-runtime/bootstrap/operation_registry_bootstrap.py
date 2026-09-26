"""Fixed wiring for application-owned deterministic operations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib import import_module
from typing import Any


OperationHandler = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class OperationRegistryBootstrapError(RuntimeError):
    """Raised when deterministic operations cannot be registered."""


def create_operation_registry(
    operations: Mapping[str, OperationHandler],
    registry: Any | None = None,
) -> Any:
    """Create and populate the framework Operation Registry.

    Operation names and functions are supplied explicitly by application
    bootstrap code. Selection is not controlled by environment variables.
    """

    if not isinstance(operations, Mapping):
        raise OperationRegistryBootstrapError(
            "operations must be a mapping"
        )

    target = registry if registry is not None else _new_registry()

    for operation_name, handler in operations.items():
        normalized_name = _operation_name(operation_name)

        if not callable(handler):
            raise OperationRegistryBootstrapError(
                f"Operation handler is not callable: {normalized_name!r}"
            )

        _register(target, normalized_name, handler)

    return target


def validate_workflow_operations(
    bundle: Any,
    operations: Mapping[str, OperationHandler],
) -> None:
    """Ensure all operation nodes declared by a bundle have handlers."""

    workflow = bundle.workflow.metadata
    nodes = workflow.get("nodes", [])

    if not isinstance(nodes, list):
        raise OperationRegistryBootstrapError(
            "Workflow nodes must be a list"
        )

    declared = {
        node.get("operation")
        for node in nodes
        if isinstance(node, Mapping)
        and node.get("type") == "operation"
    }

    missing = sorted(
        operation
        for operation in declared
        if isinstance(operation, str)
        and operation not in operations
    )

    if missing:
        raise OperationRegistryBootstrapError(
            "Missing deterministic operation handlers: "
            + ", ".join(missing)
        )


def _new_registry() -> Any:
    """Load the existing framework OperationRegistry lazily."""

    try:
        module = import_module("execution.operation_registry")
        registry_class = getattr(module, "OperationRegistry")
        return registry_class()
    except Exception as exc:
        raise OperationRegistryBootstrapError(
            "Cannot create execution.operation_registry.OperationRegistry"
        ) from exc


def _register(
    registry: Any,
    operation_name: str,
    handler: OperationHandler,
) -> None:
    """Register one handler using the existing Registry API."""

    register = getattr(registry, "register", None)

    if not callable(register):
        raise OperationRegistryBootstrapError(
            "Operation Registry must expose register()"
        )

    try:
        register(operation_name, handler)
    except Exception as exc:
        raise OperationRegistryBootstrapError(
            f"Cannot register operation {operation_name!r}"
        ) from exc


def _operation_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OperationRegistryBootstrapError(
            "Operation names must be non-empty strings"
        )
    return value.strip()
