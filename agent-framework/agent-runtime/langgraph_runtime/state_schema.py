"""Create a LangGraph state schema from a normalized JSON Schema."""

from __future__ import annotations

from typing import Any, TypedDict

from definitions import NormalizedState

from .compiler_errors import GraphCompilerError


_JSON_TYPES: dict[str, Any] = {
    "string": str,
    "boolean": bool,
    "integer": int,
    "number": float,
    "object": dict[str, Any],
    "array": list[Any],
    "null": type(None),
}


def build_state_schema(
    definition: NormalizedState,
    *,
    name: str = "CompiledAgentState",
) -> type:
    """Build a total-false TypedDict accepted by LangGraph StateGraph.

    Application fields are supplied by the registered state source. The
    compiler maps only generic JSON Schema types and does not add domain fields.
    """

    raw_properties = definition.schema.get("properties", {})
    if not isinstance(raw_properties, dict):
        raise GraphCompilerError("State properties must be a mapping")

    fields = {
        field_name: _python_type(field_name, schema)
        for field_name, schema in raw_properties.items()
    }
    return TypedDict(name, fields, total=False)


def _python_type(field_name: object, schema: object) -> Any:
    if not isinstance(field_name, str) or not field_name.strip():
        raise GraphCompilerError("State field names must be non-empty strings")
    if not isinstance(schema, dict):
        raise GraphCompilerError(
            f"State field {field_name!r} schema must be a mapping"
        )

    declared_type = schema.get("type")
    if isinstance(declared_type, list):
        members = tuple(
            _type_member(field_name, item)
            for item in declared_type
        )
        if not members:
            raise GraphCompilerError(
                f"State field {field_name!r} type list must not be empty"
            )
        result = members[0]
        for member in members[1:]:
            result = result | member
        return result

    return _type_member(field_name, declared_type)


def _type_member(field_name: str, declared_type: object) -> Any:
    if declared_type not in _JSON_TYPES:
        raise GraphCompilerError(
            f"State field {field_name!r} has unsupported JSON type: "
            f"{declared_type!r}"
        )
    return _JSON_TYPES[declared_type]
