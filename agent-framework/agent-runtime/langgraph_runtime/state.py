"""Generic graph state shared by all declarative application agents."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, TypedDict

from .errors import StateValidationError


class AgentGraphState(TypedDict, total=False):
    """Framework-owned state fields used by the central LangGraph runtime.

    Application-specific fields are allowed and remain governed by the
    application's declarative state-model definition.
    """

    conversation_id: str
    messages: list[Any]
    status: str
    application_context: dict[str, Any]
    error: dict[str, Any] | None


def validate_graph_state(
    state: dict[str, Any],
) -> None:
    """Validate only framework-owned fields without rejecting domain fields."""

    if not isinstance(state, dict):
        raise StateValidationError(
            "Graph state must be a dictionary"
        )

    _optional_non_empty_string(
        state,
        "conversation_id",
    )
    _optional_string(
        state,
        "status",
    )
    _optional_type(
        state,
        "messages",
        list,
    )
    _optional_type(
        state,
        "application_context",
        dict,
    )

    if "error" in state:
        error = state["error"]
        if error is not None and not isinstance(error, dict):
            raise StateValidationError(
                "Graph state field 'error' must be a dictionary or None"
            )


def copy_graph_state(
    state: dict[str, Any],
) -> AgentGraphState:
    """Validate and deep-copy graph state at a runtime boundary."""

    validate_graph_state(state)
    return deepcopy(state)


def _optional_non_empty_string(
    state: dict[str, Any],
    field_name: str,
) -> None:
    if field_name not in state:
        return

    value = state[field_name]
    if not isinstance(value, str) or not value.strip():
        raise StateValidationError(
            f"Graph state field {field_name!r} must be a non-empty string"
        )


def _optional_string(
    state: dict[str, Any],
    field_name: str,
) -> None:
    if field_name not in state:
        return

    if not isinstance(state[field_name], str):
        raise StateValidationError(
            f"Graph state field {field_name!r} must be a string"
        )


def _optional_type(
    state: dict[str, Any],
    field_name: str,
    expected_type: type[Any],
) -> None:
    if field_name not in state:
        return

    if not isinstance(state[field_name], expected_type):
        raise StateValidationError(
            f"Graph state field {field_name!r} must be a "
            f"{expected_type.__name__}"
        )
