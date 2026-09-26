"""Deterministic state-manipulation nodes."""
from __future__ import annotations
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Callable
from .common import public_state, read_path, require_name

Node = Callable[[dict[str, Any]], dict[str, Any]]

def create_status_node(status: str) -> Node:
    value = require_name(status, "status")
    def node(state: dict[str, Any]) -> dict[str, Any]:
        public_state(state)
        return {"status": value}
    return node

def create_assign_node(values: Mapping[str, Any]) -> Node:
    updates = {require_name(key, "state field"): deepcopy(value) for key, value in values.items()}
    def node(state: dict[str, Any]) -> dict[str, Any]:
        public_state(state)
        return deepcopy(updates)
    return node

def create_copy_node(mapping: Mapping[str, str]) -> Node:
    normalized = {require_name(target, "target field"): require_name(source, "source path") for target, source in mapping.items()}
    def node(state: dict[str, Any]) -> dict[str, Any]:
        snapshot = public_state(state)
        return {target: read_path(snapshot, source) for target, source in normalized.items()}
    return node
