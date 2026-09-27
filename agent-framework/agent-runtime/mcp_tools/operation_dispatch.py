"""Dispatch declarative operation nodes to framework-registered MCP tools.

The agent package declares which MCP tool backs each operation and how state
maps onto its arguments; endpoints stay deployment configuration.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from capabilities.capability_mapping import map_request, map_result

from .errors import MCPServerNotFoundError, MCPToolInvocationError
from .models import MCPServerRegistration


class McpOperationDispatchError(MCPToolInvocationError):
    """Raised when a declared operation cannot be dispatched."""


class McpOperationRegistry:
    """Expose agent-declared MCP operations to the workflow engine."""

    def __init__(
        self,
        declarations: Mapping[str, Mapping[str, Any]],
        servers: Mapping[str, MCPServerRegistration],
        client: Any,
    ) -> None:
        self._declarations = {
            name: dict(declaration)
            for name, declaration in declarations.items()
        }
        self._servers = dict(servers)
        self._client = client

    def names(self) -> list[str]:
        return sorted(self._declarations)

    def contains(self, name: str) -> bool:
        return isinstance(name, str) and name.strip() in self._declarations

    def invoke(
        self,
        name: str,
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Map state onto the declared tool call and return state updates."""

        if not isinstance(name, str) or not name.strip():
            raise McpOperationDispatchError(
                "Operation name must be a non-empty string"
            )

        try:
            declaration = self._declarations[name.strip()]
        except KeyError as exc:
            raise McpOperationDispatchError(
                f"Operation is not declared by the agent: {name}"
            ) from exc

        server_id = _required_text(declaration, "server", name)
        tool_name = _required_text(declaration, "tool", name)

        try:
            server = self._servers[server_id]
        except KeyError as exc:
            raise MCPServerNotFoundError(
                f"Operation {name!r} references unregistered MCP server "
                f"{server_id!r}"
            ) from exc

        arguments = map_request(declaration.get("request", {}), state)
        result = self._client.call_tool(
            server=server,
            tool_name=tool_name,
            arguments=arguments,
        )

        if result.is_error:
            raise McpOperationDispatchError(
                f"MCP tool {tool_name!r} reported an error for operation "
                f"{name!r}"
            )

        structured = result.structured_content
        if structured is None:
            raise McpOperationDispatchError(
                f"MCP tool {tool_name!r} returned no structured content"
            )

        return map_result(declaration.get("result", {}), structured)


def load_operation_declarations(
    bundle: Any,
) -> dict[str, dict[str, Any]]:
    """Read the operation-to-tool bindings declared by an agent package."""

    metadata = bundle.capabilities.metadata
    declared = metadata.get("operations", [])

    if not isinstance(declared, list):
        raise McpOperationDispatchError(
            "Agent operations declaration must be a list"
        )

    declarations: dict[str, dict[str, Any]] = {}
    for declaration in declared:
        if not isinstance(declaration, Mapping):
            raise McpOperationDispatchError(
                "Each operation declaration must be a mapping"
            )
        identifier = declaration.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise McpOperationDispatchError(
                "Operation declaration must contain a non-empty ID"
            )
        if identifier.strip() in declarations:
            raise McpOperationDispatchError(
                f"Duplicate operation declaration: {identifier}"
            )
        declarations[identifier.strip()] = dict(declaration)

    return declarations


def _required_text(
    declaration: Mapping[str, Any],
    field: str,
    operation: str,
) -> str:
    value = declaration.get(field)
    if not isinstance(value, str) or not value.strip():
        raise McpOperationDispatchError(
            f"Operation {operation!r} must declare {field!r}"
        )
    return value.strip()
