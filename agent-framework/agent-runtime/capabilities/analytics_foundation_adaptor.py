"""Adapt declarative agent capabilities to Analytics Foundation clients."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from analytics_foundation_clients.protocols import (
    AnalyticsFoundationClient,
)

from execution.definition_loader import (
    AgentDefinitionBundle,
)

from .capability_mapping import (
    map_request,
    map_result,
)
from .capability_models import (
    CapabilityContext,
)
from .capability_registry import (
    CapabilityRegistry,
)


class AnalyticsFoundationAdaptorError(ValueError):
    """Raised when Analytics Foundation capabilities cannot be configured."""


class AnalyticsFoundationAdaptor:
    """Connect agent-declared capabilities to Analytics Foundation clients."""

    def __init__(
        self,
        bundle: AgentDefinitionBundle,
        client: AnalyticsFoundationClient,
        *,
        registry: CapabilityRegistry | None = None,
    ) -> None:
        self.bundle = bundle
        self.client = client
        self.registry = registry or CapabilityRegistry()

        self._declarations = (
            self._load_capability_declarations()
        )

    def register_declared_capabilities(
        self,
    ) -> CapabilityRegistry:
        """Register all capabilities declared by the selected agent."""

        for capability_id in self.declared_capability_ids():
            declaration = self._declarations[
                capability_id
            ]

            operation = self._required_text(
                declaration,
                "operation",
                capability_id,
            )

            handler = self._create_handler(operation)

            self.registry.register(
                capability_id=capability_id,
                operation=operation,
                handler=handler,
                description=str(
                    declaration.get(
                        "description",
                        "",
                    )
                ),
                owner=str(
                    declaration.get(
                        "owner",
                        "",
                    )
                ),
                version=str(
                    declaration.get(
                        "version",
                        "1.0",
                    )
                ),
                required_permissions=declaration.get(
                    "permissions",
                    [],
                ),
                approval_required=declaration.get(
                    "approval_required",
                    False,
                ),
                side_effect=declaration.get(
                    "side_effect",
                    False,
                ),
            )

        return self.registry

    def declared_capability_ids(self) -> list[str]:
        """Return agent-declared capability IDs."""

        return sorted(self._declarations)

    def invoke(
        self,
        capability_id: str,
        state: Mapping[str, Any],
        *,
        context: CapabilityContext | None = None,
    ) -> dict[str, Any]:
        """Invoke a declared capability using workflow state."""

        declaration = self._get_declaration(
            capability_id
        )

        request_mapping = declaration.get(
            "request",
            {},
        )

        result_mapping = declaration.get(
            "result",
            {},
        )

        request = map_request(
            request_mapping,
            state,
        )

        result = self.registry.invoke(
            capability_id,
            request,
            context=context,
        )

        return map_result(
            result_mapping,
            result,
        )

    def _load_capability_declarations(
        self,
    ) -> dict[str, dict[str, Any]]:
        """Index the capability declarations by logical ID."""

        capabilities = (
            self.bundle.capabilities.metadata.get(
                "capabilities"
            )
        )

        if not isinstance(capabilities, list):
            raise AnalyticsFoundationAdaptorError(
                "Agent capability definition must contain "
                "a capabilities list"
            )

        declarations: dict[
            str,
            dict[str, Any],
        ] = {}

        for declaration in capabilities:
            if not isinstance(declaration, dict):
                raise AnalyticsFoundationAdaptorError(
                    "Each capability declaration must "
                    "be a mapping"
                )

            capability_id = declaration.get("id")

            if (
                not isinstance(capability_id, str)
                or not capability_id.strip()
            ):
                raise AnalyticsFoundationAdaptorError(
                    "Capability declaration must contain "
                    "a non-empty ID"
                )

            normalized_id = capability_id.strip()

            if normalized_id in declarations:
                raise AnalyticsFoundationAdaptorError(
                    f"Duplicate capability declaration: "
                    f"{normalized_id}"
                )

            declarations[normalized_id] = deepcopy(
                declaration
            )

        return declarations

    def _get_declaration(
        self,
        capability_id: str,
    ) -> dict[str, Any]:
        """Return one ."""

        if (
            not isinstance(capability_id, str)
            or not capability_id.strip()
        ):
            raise AnalyticsFoundationAdaptorError(
                "Capability ID must be a non-empty string"
            )

        normalized_id = capability_id.strip()

        try:
            return self._declarations[normalized_id]
        except KeyError as exc:
            raise AnalyticsFoundationAdaptorError(
                f"Capability is not declared by the agent: "
                f"{normalized_id}"
            ) from exc

    def _create_handler(
        self,
        operation: str,
    ):
        """Create a registry handler for one client operation."""

        def handler(
            request: Mapping[str, Any],
        ) -> dict[str, Any]:
            return self.client.invoke(
                operation,
                request,
            )

        return handler

    @staticmethod
    def _required_text(
        mapping: Mapping[str, Any],
        field_name: str,
        capability_id: str,
    ) -> str:
        """Read a required text field from a declaration."""

        value = mapping.get(field_name)

        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise AnalyticsFoundationAdaptorError(
                f"Capability {capability_id!r} must declare "
                f"a non-empty {field_name!r}"
            )

        return value.strip()