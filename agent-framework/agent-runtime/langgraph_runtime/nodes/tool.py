"""Standard governed tool node."""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any, Callable
from .common import build_arguments, public_state, require_mapping, require_name
from .errors import StandardNodeExecutionError


def create_tool_node(
    *,
    dependencies: Any,
    tool_id: str,
    input_mapping: Mapping[str, str],
    output_field: str,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    identifier = require_name(tool_id, "tool_id")
    target = require_name(output_field, "output_field")
    mapping = {require_name(k, "tool argument"): require_name(v, "state path") for k, v in input_mapping.items()}

    def node(state: dict[str, Any]) -> dict[str, Any]:
        snapshot = public_state(state)
        arguments = build_arguments(snapshot, mapping)
        try:
            result = dependencies.tool_registry.invoke(
                tool_id=identifier,
                arguments=arguments,
                state=snapshot,
                security_context=dependencies.security_context,
            )
        except Exception as exc:
            raise StandardNodeExecutionError(
                f"Governed tool node failed for {identifier!r}"
            ) from exc
        return {target: dict(require_mapping(result, "tool result"))}
    return node
