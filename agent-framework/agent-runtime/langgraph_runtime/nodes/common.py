"""Shared helpers for standard LangGraph nodes."""
from __future__ import annotations
from collections.abc import Mapping
from copy import deepcopy
from typing import Any
from langgraph_runtime.nodes.errors import StandardNodeConfigurationError, StandardNodeExecutionError
from langgraph_runtime.state import copy_graph_state


def require_name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StandardNodeConfigurationError(f"{label} must be a non-empty string")
    return value.strip()


def require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StandardNodeExecutionError(f"{label} must be a mapping")
    return value


def read_path(state: Mapping[str, Any], path: str) -> Any:
    current: Any = state
    for part in require_name(path, "state path").split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise StandardNodeExecutionError(f"State path is unavailable: {path!r}")
        current = current[part]
    return deepcopy(current)


def build_arguments(state: Mapping[str, Any], mapping: Mapping[str, str]) -> dict[str, Any]:
    return {str(target): read_path(state, source) for target, source in mapping.items()}


def public_state(state: Mapping[str, Any]) -> dict[str, Any]:
    return dict(copy_graph_state(dict(state)))
