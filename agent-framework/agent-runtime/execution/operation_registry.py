"""Register and invoke deterministic application operations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from inspect import iscoroutinefunction
from types import MappingProxyType
from typing import Any


WorkflowState = Mapping[str, Any]
StateUpdate = dict[str, Any]
OperationHandler = Callable[[WorkflowState], StateUpdate]


class OperationRegistryError(ValueError):
    """Base error raised by the Operation Registry."""


class OperationAlreadyRegisteredError(OperationRegistryError):
    """Raised when an operation name is registered more than once."""


class OperationNotFoundError(OperationRegistryError):
    """Raised when a requested operation is not registered."""


class InvalidOperationError(OperationRegistryError):
    """Raised when an operation declaration or result is invalid."""


class OperationExecutionError(RuntimeError):
    """Raised when an operation handler fails during execution."""


@dataclass(frozen=True)
class OperationDefinition:
    """Metadata and handler for one deterministic operation."""

    name: str
    handler: OperationHandler
    description: str = ""
    owner: str = ""
    version: str = "1.0"

    def as_dict(self) -> dict[str, str]:
        """Return public metadata without exposing the handler."""

        return {
            "name": self.name,
            "description": self.description,
            "owner": self.owner,
            "version": self.version,
        }


class OperationRegistry:
    """Registry for synchronous deterministic application operations."""

    def __init__(self) -> None:
        self._operations: dict[str, OperationDefinition] = {}

    def register(
        self,
        name: str,
        handler: OperationHandler,
        *,
        description: str = "",
        owner: str = "",
        version: str = "1.0",
        replace: bool = False,
    ) -> OperationDefinition:
        """Register one deterministic operation."""

        normalized_name = self._validate_name(name)
        self._validate_handler(normalized_name, handler)

        if normalized_name in self._operations and not replace:
            raise OperationAlreadyRegisteredError(
                f"Operation is already registered: {normalized_name}"
            )

        definition = OperationDefinition(
            name=normalized_name,
            handler=handler,
            description=self._validate_optional_string(
                description,
                "description",
                normalized_name,
            ),
            owner=self._validate_optional_string(
                owner,
                "owner",
                normalized_name,
            ),
            version=self._validate_required_string(
                version,
                "version",
                normalized_name,
            ),
        )

        self._operations[normalized_name] = definition
        return definition

    def unregister(self, name: str) -> OperationDefinition:
        """Remove and return a registered operation."""

        normalized_name = self._validate_name(name)

        try:
            return self._operations.pop(normalized_name)
        except KeyError as exc:
            raise OperationNotFoundError(
                f"Operation is not registered: {normalized_name}"
            ) from exc

    def contains(self, name: str) -> bool:
        """Return whether an operation is registered."""

        if not isinstance(name, str):
            return False

        normalized_name = name.strip()

        return (
            bool(normalized_name)
            and normalized_name in self._operations
        )

    def resolve(self, name: str) -> OperationDefinition:
        """Resolve one operation by name."""

        normalized_name = self._validate_name(name)

        try:
            return self._operations[normalized_name]
        except KeyError as exc:
            raise OperationNotFoundError(
                f"Operation is not registered: {normalized_name}"
            ) from exc

    def names(self) -> list[str]:
        """Return registered operation names in sorted order."""

        return sorted(self._operations)

    def list(self) -> list[dict[str, str]]:
        """Return public metadata for all registered operations."""

        return [
            self._operations[name].as_dict()
            for name in self.names()
        ]

    def invoke(
        self,
        name: str,
        state: Mapping[str, Any],
    ) -> StateUpdate:
        """Invoke an operation and return workflow-state updates."""

        definition = self.resolve(name)
        protected_state = self._protect_state(state)

        try:
            result = definition.handler(protected_state)
        except OperationRegistryError:
            raise
        except Exception as exc:
            raise OperationExecutionError(
                f"Operation {definition.name!r} failed: {exc}"
            ) from exc

        return self._validate_result(
            definition.name,
            result,
        )

    def operation(
        self,
        name: str,
        *,
        description: str = "",
        owner: str = "",
        version: str = "1.0",
        replace: bool = False,
    ) -> Callable[[OperationHandler], OperationHandler]:
        """Return a decorator that registers an operation handler."""

        def decorator(
            handler: OperationHandler,
        ) -> OperationHandler:
            self.register(
                name=name,
                handler=handler,
                description=description,
                owner=owner,
                version=version,
                replace=replace,
            )

            return handler

        return decorator

    @staticmethod
    def _protect_state(
        state: Mapping[str, Any],
    ) -> WorkflowState:
        """Return a protected copy of workflow state.

        The topead-only. Nested objects are deep-copied,
        preventing an operation from changing the original workflow state.
        """

        if not isinstance(state, Mapping):
            raise InvalidOperationError(
                "Workflow state must be a mapping"
            )

        copied_state = deepcopy(dict(state))

        return MappingProxyType(copied_state)

    @staticmethod
    def _validate_result(
        operation_name: str,
        result: Any,
    ) -> StateUpdate:
        """Validate and copy an operation result."""

        if not isinstance(result, dict):
            raise InvalidOperationError(
                f"Operation {operation_name!r} must return "
                "a dictionary of state updates"
            )

        for field_name in result:
            if not isinstance(field_name, str):
                raise InvalidOperationError(
                    f"Operation {operation_name!r} returned "
                    "a state update with a non-string field name"
                )

            if not field_name.strip():
                raise InvalidOperationError(
                    f"Operation {operation_name!r} returned "
                    "an empty state field name"
                )

        return deepcopy(result)

    @staticmethod
    def _validate_name(name: str) -> str:
        """Validate and normalize an operation name."""

        if not isinstance(name, str):
            raise InvalidOperationError(
                "Operation name must be a string"
            )

        normalized_name = name.strip()

        if not normalized_name:
            raise InvalidOperationError(
                "Operation name must not be empty"
            )

        return normalized_name

    @staticmethod
    def _validate_handler(
        name: str,
        handler: OperationHandler,
    ) -> None:
        """Validate an operation handler."""

        if not callable(handler):
            raise InvalidOperationError(
                f"Handler for operation {name!r} must be callable"
            )

        if iscoroutinefunction(handler):
            raise InvalidOperationError(
                f"Handler for operation {name!r} is asynchronous. "
                "The synchronous Operation Registry only accepts "
                "synchronous handlers."
            )

    @staticmethod
    def _validate_optional_string(
        value: str,
        field_name: str,
        operation_name: str,
    ) -> str:
        """Validate optional textual operation metadata."""

        if not isinstance(value, str):
            raise InvalidOperationError(
                f"{field_name} for operation "
                f"{operation_name!r} must be a string"
            )

        return value.strip()

    @classmethod
    def _validate_required_string(
        cls,
        value: str,
        field_name: str,
        operation_name: str,
    ) -> str:
        """Validate required textual operation metadata."""

        normalized_value = cls._validate_optional_string(
            value,
            field_name,
            operation_name,
        )

        if not normalized_value:
            raise InvalidOperationError(
                f"{field_name} for operation "
                f"{operation_name!r} must not be empty"
            )

        return normalized_value