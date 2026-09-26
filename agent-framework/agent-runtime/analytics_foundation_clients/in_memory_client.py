"""In-memory Analytics Foundation client for tests and local execution."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from types import MappingProxyType
from typing import Any


AnalyticsFoundationHandler = Callable[
    [Mapping[str, Any]],
    dict[str, Any],
]


class AnalyticsFoundationClientError(RuntimeError):
    """Base error raised by an Analytics Foundation client."""


class AnalyticsFoundationOperationNotFoundError(
    AnalyticsFoundationClientError
):
    """Raised when an operation has no configured handler."""


class AnalyticsFoundationInvalidResultError(
    AnalyticsFoundationClientError
):
    """Raised when an operation returns an invalid result."""


class InMemoryAnalyticsFoundationClient:
    """Dispatch Analytics Foundation operations to in-memory handlers."""

    def __init__(self) -> None:
        self._handlers: dict[
            str,
            AnalyticsFoundationHandler,
        ] = {}

    def register(
        self,
        operation: str,
        handler: AnalyticsFoundationHandler,
        *,
        replace: bool = False,
    ) -> None:
        """Register one Analytics Foundation operation handler."""

        normalized_operation = self._validate_operation(
            operation
        )

        if not callable(handler):
            raise AnalyticsFoundationClientError(
                f"Handler for operation "
                f"{normalized_operation!r} must be callable"
            )

        if (
            normalized_operation in self._handlers
            and not replace
        ):
            raise AnalyticsFoundationClientError(
                f"Operation is already registered: "
                f"{normalized_operation}"
            )

        self._handlers[normalized_operation] = handler

    def contains(
        self,
        operation: str,
    ) -> bool:
        """Return whether an operation handler is registered."""

        return (
            isinstance(operation, str)
            and bool(operation.strip())
            and operation.strip() in self._handlers
        )

    def operations(self) -> list[str]:
        """Return operation names in sorted order."""

        return sorted(self._handlers)

    def invoke(
        self,
        operation: str,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Invoke one registered Analytics Foundation operation."""

        normalized_operation = self._validate_operation(
            operation
        )

        if not isinstance(request, Mapping):
            raise AnalyticsFoundationClientError(
                "Analytics Foundation request must be a mapping"
            )

        try:
            handler = self._handlers[normalized_operation]
        except KeyError as exc:
            raise AnalyticsFoundationOperationNotFoundError(
                "Analytics Foundation operation is not registered: "
                f"{normalized_operation}"
            ) from exc

        protected_request = MappingProxyType(
            deepcopy(dict(request))
        )

        result = handler(protected_request)

        if not isinstance(result, dict):
            raise AnalyticsFoundationInvalidResultError(
                f"Analytics Foundation operation "
                f"{normalized_operation!r} must return a dictionary"
            )

        for field_name in result:
            if (
                not isinstance(field_name, str)
                or not field_name.strip()
            ):
                raise AnalyticsFoundationInvalidResultError(
                    f"Analytics Foundation operation "
                    f"{normalized_operation!r} returned an invalid "
                    "field name"
                )

        return deepcopy(result)

    @staticmethod
    def _validate_operation(
        operation: str,
    ) -> str:
        """Validate and normalize an operation name."""

        if (
            not isinstance(operation, str)
            or not operation.strip()
        ):
            raise AnalyticsFoundationClientError(
                "Analytics Foundation operation must be "
                "a non-empty string"
            )

        return operation.strip()
