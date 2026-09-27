"""Resolve declared MCP server identifiers to deployment endpoints.

Agent packages name servers; endpoints stay deployment configuration, so the
same declarative package runs against local, test, and production servers.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping

from .errors import MCPServerNotFoundError
from .models import MCPServerRegistration

DEFAULT_TIMEOUT_SECONDS = 30.0


def environment_variable_for(server_id: str) -> str:
    """Return the variable holding one server's endpoint."""

    normalized = server_id.strip().upper().replace("-", "_")
    return f"{normalized}_MCP_URL"


def registrations_from_environment(
    server_ids: Iterable[str],
    environment: Mapping[str, str] | None = None,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, MCPServerRegistration]:
    """Build registrations for every server an agent package references."""

    env = dict(os.environ if environment is None else environment)
    registrations: dict[str, MCPServerRegistration] = {}

    for server_id in server_ids:
        identifier = server_id.strip()
        if not identifier:
            raise MCPServerNotFoundError(
                "MCP server identifier must be a non-empty string"
            )

        variable = environment_variable_for(identifier)
        endpoint = env.get(variable, "").strip()
        if not endpoint:
            raise MCPServerNotFoundError(
                f"MCP server {identifier!r} has no endpoint: set {variable}"
            )

        registrations[identifier] = MCPServerRegistration(
            server_id=identifier,
            display_name=identifier,
            transport="http",
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
        )

    return registrations
