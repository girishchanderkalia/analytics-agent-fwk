
###############################################################################
# expression_evaluator.py
###############################################################################

"""Evaluate declarative workflow-routing conditions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from .execution_models import RoutingError


SUPPORTED_OPERATORS = frozenset(
    {
        "equals",
        "not_equals",
        "empty",
        "not_empty",
        "greater_than",
        "greater_than_or_equal",
        "less_than",
        "less_than_or_equal",
        "is_null",
        "is_not_null",
    }
)


def resolve_path(
    state: Mapping[str, Any],
    field_path: str,
) -> Any:
    """Resolve a dotted field path from workflow state."""

    if not isinstance(field_path, str) or not field_path.strip():
        raise RoutingError(
            "Routing field path must be a non-empty string"
        )

    current: Any = state

    for segment in field_path.split("."):
        if not isinstance(current, Mapping):
            return None

        if segment not in current:
            return None

        current = current[segment]

    return current


def evaluate_condition(
    condition: Mapping[str, Any],
    state: Mapping[str, Any],
    defaults: Mapping[str, Any] | None = None,
) -> bool:
    """Evaluate one declarative routing condition."""

    field_path = condition.get("field")
    operator = condition.get("operator")

    if not isinstance(field_path, str) or not field_path:
        raise RoutingError(
            "Routing condition must declare a field"
        )

    if operator not in SUPPORTED_OPERATORS:
        raise RoutingError(
            f"Unsupported routing operator {operator!r}"
        )

    actual = resolve_path(state, field_path)

    if "value_from" in condition:
        expected = _resolve_value_from(
            condition["value_from"],
            defaults or {},
        )
    else:
        expected = condition.get("value")

    if operator == "equals":
        return actual == expected

    if operator == "not_equals":
        return actual != expected

    if operator == "empty":
        return actual in (None, "", [], {}, ())

    if operator == "not_empty":
        return actual not in (None, "", [], {}, ())

    if operator == "is_null":
        return actual is None

    if operator == "is_not_null":
        return actual is not None

    if operator == "greater_than":
        return _compare(actual, expected, operator)

    if operator == "greater_than_or_equal":
        return _compare(actual, expected, operator)

    if operator == "less_than":
        return _compare(actual, expected, operator)

    if operator == "less_than_or_equal":
        return _compare(actual, expected, operator)

    raise RoutingError(
        f"Routing operator {operator!r} was not evaluated"
    )


def apply_state_update(
    state: dict[str, Any],
    state_update: Mapping[str, Any] | None,
) -> None:
    """Apply a declarative routing state update."""

    if not state_update:
        return

    for field_name, update in state_update.items():
        if (
            isinstance(update, Mapping)
            and update.get("operation") == "increment"
        ):
            increment = update.get("value", 1)
            current = state.get(field_name, 0)

            if not isinstance(current, (int, float)):
                raise RoutingError(
                    f"Cannot increment non-numeric field "
                    f"{field_name!r}"
                )

            if not isinstance(increment, (int, float)):
                raise RoutingError(
                    f"Increment for field {field_name!r} "
                    "must be numeric"
                )

            state[field_name] = current + increment
        else:
            state[field_name] = update


def _resolve_value_from(
    value_from: Any,
    defaults: Mapping[str, Any],
) -> Any:
    if not isinstance(value_from, str) or not value_from:
        raise RoutingError(
            "Routing value_from must be a non-empty string"
        )

    path = value_from

    if path.startswith("defaults."):
        path = path[len("defaults.") :]

    return resolve_path(defaults, path)


def _compare(
    actual: Any,
    expected: Any,
    operator: str,
) -> bool:
    if actual is None or expected is None:
        return False

    try:
        if operator == "greater_than":
            return actual > expected

        if operator == "greater_than_or_equal":
            return actual >= expected

        if operator == "less_than":
            return actual < expected

        if operator == "less_than_or_equal":
            return actual <= expected
    except TypeError as exc:
        raise RoutingError(
            f"Cannot evaluate {actual!r} {operator} "
            f"{expected!r}"
        ) from exc

    return False
