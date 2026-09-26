"""Map workflow state to capability requests and results to state updates."""

from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any


REFERENCE_PATTERN = re.compile(
    r"^\$\{(?P<root>state|result)"
    r"(?P<path>(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\}$"
)


class CapabilityMappingError(ValueError):
    """Raised when a capability mapping cannot be resolved."""


def resolve_reference(
    expression: str,
    *,
    state: Mapping[str, Any] | None = None,
    result: Mapping[str, Any] | None = None,
) -> Any:
    """Resolve a state or result expression."""

    if not isinstance(expression, str):
        raise CapabilityMappingError(
            "Capability reference must be a string"
        )

    match = REFERENCE_PATTERN.fullmatch(
        expression.strip()
    )

    if match is None:
        raise CapabilityMappingError(
            f"Invalid capability reference: {expression!r}"
        )

    root_name = match.group("root")
    path_text = match.group("path")

    source: Mapping[str, Any] | None

    if root_name == "state":
        source = state
    else:
        source = result

    if source is None:
        raise CapabilityMappingError(
            f"No {root_name} value is available for "
            f"reference {expression!r}"
        )

    path_parts = [
        part
        for part in path_text.split(".")
        if part
    ]

    current: Any = source

    for part in path_parts:
        if not isinstance(current, Mapping):
            raise CapabilityMappingError(
                f"Cannot resolve {expression!r}: "
                f"{part!r} is not inside a mapping"
            )

        if part not in current:
            raise CapabilityMappingError(
                f"Cannot resolve {expression!r}: "
                f"field {part!r} is missing"
            )

        current = current[part]

    return deepcopy(current)


def map_value(
    value: Any,
    *,
    state: Mapping[str, Any] | None = None,
    result: Mapping[str, Any] | None = None,
) -> Any:
    """Recursively map references inside a value."""

    if isinstance(value, str):
        if value.strip().startswith("${"):
            return resolve_reference(
                value,
                state=state,
                result=result,
            )

        return value

    if isinstance(value, list):
        return [
            map_value(
                item,
                state=state,
                result=result,
            )
            for item in value
        ]

    if isinstance(value, Mapping):
        return {
            key: map_value(
                item,
                state=state,
                result=result,
            )
            for key, item in value.items()
        }

    return deepcopy(value)


def map_request(
    request_mapping: Mapping[str, Any],
    state: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a capability request from workflow state."""

    if not isinstance(request_mapping, Mapping):
        raise CapabilityMappingError(
            "Capability request mapping must be a mapping"
        )

    if not isinstance(state, Mapping):
        raise CapabilityMappingError(
            "Workflow state must be a mapping"
        )

    mapped = map_value(
        request_mapping,
        state=state,
    )

    if not isinstance(mapped, dict):
        raise CapabilityMappingError(
            "Mapped capability request must be a dictionary"
        )

    return mapped


def map_result(
    result_mapping: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Create workflow-state updates from a capability result."""

    if not isinstance(result_mapping, Mapping):
        raise CapabilityMappingError(
            "Capability result mapping must be a mapping"
        )

    if not isinstance(result, Mapping):
        raise CapabilityMappingError(
            "Capability result must be a mapping"
        )

    state_updates: dict[str, Any] = {}

    for state_field, expression in result_mapping.items():
        if (
            not isinstance(state_field, str)
            or not state_field.strip()
        ):
            raise CapabilityMappingError(
                "Capability result mapping contains "
                "an invalid state field"
            )

        state_updates[state_field.strip()] = map_value(
            expression,
            result=result,
        )

    return state_updates