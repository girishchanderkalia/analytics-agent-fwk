"""Register, authorize, and invoke external platform capabilities."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from copy import deepcopy
from inspect import iscoroutinefunction
from types import MappingProxyType
from typing import Any
from collections.abc import Collection

from .capability_models import (
    CapabilityContext,
    CapabilityDefinition,
    CapabilityHandler,
    CapabilityInvocation,
    CapabilityResult,
)


class CapabilityRegistryError(ValueError):
    """Base error raised by the Capability Registry."""


class CapabilityAlreadyRegisteredError(
    CapabilityRegistryError
):
    """Raised when a capability ID is registered more than once."""


class CapabilityNotFoundError(CapabilityRegistryError):
    """Raised when a requested capability is not registered."""


class InvalidCapabilityError(CapabilityRegistryError):
    """Raised when a capability declaration or result is invalid."""


class CapabilityPermissionError(PermissionError):
    """Raised when required permissions are missing."""


class CapabilityApprovalError(PermissionError):
    """Raised when a capability requires approval."""


class CapabilityExecutionError(RuntimeError):
    """Raised when a capability handler fails."""


class CapabilityRegistry:
    """Registry for governed synchronous external capabilities."""

    def __init__(self) -> None:
        self._capabilities: dict[
            str,
            CapabilityDefinition,
        ] = {}

    def register(
        self,
        capability_id: str,
        operation: str,
        handler: CapabilityHandler,
        *,
        description: str = "",
        owner: str = "",
        version: str = "1.0",
        required_permissions: Collection[str] | None = None,
        approval_required: bool = False,
        side_effect: bool = False,
        replace: bool = False,
    ) -> CapabilityDefinition:
        """Register one capability implementation."""

        normalized_id = self._required_text(
            capability_id,
            "capability_id",
        )

        normalized_operation = self._required_text(
            operation,
            "operation",
        )

        normalized_version = self._required_text(
            version,
            "version",
        )

        normalized_description = self._optional_text(
            description,
            "description",
        )

        normalized_owner = self._optional_text(
            owner,
            "owner",
        )

        permissions = self._normalize_permissions(
            required_permissions
        )

        self._validate_handler(
            normalized_id,
            handler,
        )

        if not isinstance(approval_required, bool):
            raise InvalidCapabilityError(
                "approval_required must be a boolean"
            )

        if not isinstance(side_effect, bool):
            raise InvalidCapabilityError(
                "side_effect must be a boolean"
            )

        if (
            normalized_id in self._capabilities
            and not replace
        ):
            raise CapabilityAlreadyRegisteredError(
                "Capability is already registered: "
                f"{normalized_id}"
            )

        definition = CapabilityDefinition(
            capability_id=normalized_id,
            operation=normalized_operation,
            handler=handler,
            description=normalized_description,
            owner=normalized_owner,
            version=normalized_version,
            required_permissions=permissions,
            approval_required=approval_required,
            side_effect=side_effect,
        )

        self._capabilities[normalized_id] = definition

        return definition

    def unregister(
        self,
        capability_id: str,
    ) -> CapabilityDefinition:
        """Remove and return a registered capability."""

        normalized_id = self._required_text(
            capability_id,
            "capability_id",
        )

        try:
            return self._capabilities.pop(normalized_id)
        except KeyError as exc:
            raise CapabilityNotFoundError(
                "Capability is not registered: "
                f"{normalized_id}"
            ) from exc

    def contains(
        self,
        capability_id: str,
    ) -> bool:
        """Return whether a capability is registered."""

        return (
            isinstance(capability_id, str)
            and bool(capability_id.strip())
            and capability_id.strip() in self._capabilities
        )

    def resolve(
        self,
        capability_id: str,
    ) -> CapabilityDefinition:
        """Resolve a capability by logical capability ID."""

        normalized_id = self._required_text(
            capability_id,
            "capability_id",
        )

        try:
            return self._capabilities[normalized_id]
        except KeyError as exc:
            raise CapabilityNotFoundError(
                "Capability is not registered: "
                f"{normalized_id}"
            ) from exc

    def names(self) -> list[str]:
        """Return registered capability IDs in sorted order."""     
        return sorted(self._capabilities)

    def list(self) -> list[dict[str, Any]]:
        """Return public metadata for every capability."""

        return [
            self._capabilities[name].as_dict()
            for name in self.names()
        ]

    def invoke(
        self,
        capability_id: str,
        request: Mapping[str, Any],
        *,
        context: CapabilityContext | None = None,
    ) -> CapabilityResult:
        """Authorize and invoke one registered capability."""

        invocation = CapabilityInvocation(
            capability_id=capability_id,
            request=request,
            context=context or CapabilityContext(),
        )

        definition = self.resolve(
            invocation.capability_id
        )

        self._authorize(
            definition,
            invocation.context,
        )

        protected_request = self._protect_request(
            invocation.request
        )

        try:
            result = definition.handler(
                protected_request
            )
        except CapabilityRegistryError:
            raise
        except Exception as exc:
            raise CapabilityExecutionError(
                f"Capability "
                f"{definition.capability_id!r} failed: {exc}"
            ) from exc

        return self._validate_result(
            definition.capability_id,
            result,
        )

    @staticmethod
    def _authorize(
        definition: CapabilityDefinition,
        context: CapabilityContext,
    ) -> None:
        """Enforce permissions and approval requirements."""

        missing_permissions = (
            definition.required_permissions
            - context.permissions
        )

        if missing_permissions:
            raise CapabilityPermissionError(
                f"Capability "
                f"{definition.capability_id!r} requires "
                f"permissions: {sorted(missing_permissions)}"
            )

        if (
            definition.approval_required
            and not context.approved
        ):
            raise CapabilityApprovalError(
                f"Capability "
                f"{definition.capability_id!r} "
                "requires approval"
            )

    @staticmethod
    def _protect_request(
        request: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Return a protected copy of the capability request."""

        if not isinstance(request, Mapping):
            raise InvalidCapabilityError(
                "Capability request must be a mapping"
            )

        copied_request = deepcopy(dict(request))

        return MappingProxyType(copied_request)

    @staticmethod
    def _validate_result(
        capability_id: str,
        result: Any,
    ) -> CapabilityResult:
        """Validate and copy a capability result."""

        if not isinstance(result, dict):
            raise InvalidCapabilityError(
                f"Capability {capability_id!r} "
                "must return a dictionary"
            )

        for field_name in result:
            if (
                not isinstance(field_name, str)
                or not field_name.strip()
            ):
                raise InvalidCapabilityError(
                    f"Capability {capability_id!r} "
                    "returned an invalid field name"
                )

        return deepcopy(result)

    @staticmethod
    def _validate_handler(
        capability_id: str,
        handler: CapabilityHandler,
    ) -> None:
        """Validate one capability handler."""

        if not callable(handler):
            raise InvalidCapabilityError(
                f"Handler for capability "
                f"{capability_id!r} must be callable"
            )

        if iscoroutinefunction(handler):
            raise InvalidCapabilityError(
                f"Handler for capability "
                f"{capability_id!r} is asynchronous"
            )

    @staticmethod
    def _normalize_permissions(
    permissions: Collection[str] | None,
) -> frozenset[str]:
        """Validate and normalize required permissions."""

        if permissions is None:
            return frozenset()

        if isinstance(permissions, str):
            raise InvalidCapabilityError(
                "required_permissions must be a "
                "collection of strings"
            )

        normalized: set[str] = set()

        for permission in permissions:
            if not isinstance(permission, str):
                raise InvalidCapabilityError(
                    "required_permissions must contain "
                    "only strings"
                )

            normalized_permission = permission.strip()

            if not normalized_permission:
                raise InvalidCapabilityError(
                    "required_permissions must contain "
                    "non-empty strings"
                )

            normalized.add(normalized_permission)

        return frozenset(normalized)

    @staticmethod
    def _required_text(
        value: str,
        field_name: str,
    ) -> str:
        """Validate and normalize required text."""

        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise InvalidCapabilityError(
                f"{field_name} must be a non-empty string"
            )

        return value.strip()

    @staticmethod
    def _optional_text(
        value: str,
        field_name: str,
    ) -> str:
        """Validate and normalize optional text."""

        if not isinstance(value, str):
            raise InvalidCapabilityError(
                f"{field_name} must be a string"
            )

        return value.strip()