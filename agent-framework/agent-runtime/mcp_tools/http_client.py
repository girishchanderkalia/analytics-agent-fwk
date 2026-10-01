"""JSON-RPC MCP client used by the framework to reach registered servers.

Only the framework talks to MCP servers; applications never do.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .client import MCPDiscoveredTool, MCPToolResult
from .errors import MCPToolInvocationError
from .models import MCPServerRegistration


logger = logging.getLogger(__name__)


class HttpMcpClient:
    """Call MCP servers over HTTP JSON-RPC."""

    def __init__(self, default_timeout_seconds: float = 30.0) -> None:
        self.default_timeout_seconds = default_timeout_seconds

    def list_tools(
        self,
        *,
        server: MCPServerRegistration,
    ) -> tuple[MCPDiscoveredTool, ...]:
        """Discover the tools a server publishes."""

        result = self._call(
            server=server,
            method="tools/list",
            params={},
            timeout_seconds=server.timeout_seconds,
        )
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise MCPToolInvocationError(
                f"MCP server {server.server_id!r} returned no tool list"
            )
        return tuple(
            MCPDiscoveredTool(
                name=str(tool.get("name", "")),
                title=tool.get("title"),
                description=tool.get("description"),
                input_schema=tool.get("inputSchema") or {},
            )
            for tool in tools
            if isinstance(tool, Mapping)
        )

    def call_tool(
        self,
        *,
        server: MCPServerRegistration,
        tool_name: str,
        arguments: Mapping[str, Any],
        timeout_seconds: float | None = None,
    ) -> MCPToolResult:
        """Invoke one tool and return its structured content."""

        result = self._call(
            server=server,
            method="tools/call",
            params={"name": tool_name, "arguments": dict(arguments)},
            timeout_seconds=timeout_seconds or server.timeout_seconds,
        )

        structured = result.get("structuredContent")
        if structured is not None and not isinstance(structured, Mapping):
            raise MCPToolInvocationError(
                f"MCP tool {tool_name!r} returned invalid structured content"
            )

        content = result.get("content")
        return MCPToolResult(
            content=tuple(
                item for item in content or () if isinstance(item, Mapping)
            ),
            structured_content=(
                dict(structured) if structured is not None else None
            ),
            is_error=bool(result.get("isError", False)),
        )

    def _call(
        self,
        *,
        server: MCPServerRegistration,
        method: str,
        params: Mapping[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": f"{server.server_id}:{method}",
                "method": method,
                "params": dict(params),
            }
        ).encode("utf-8")

        request = Request(
            server.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        started = perf_counter()
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, OSError, ValueError) as exc:
            raise MCPToolInvocationError(
                f"MCP call {method!r} to {server.server_id!r} failed: {exc}"
            ) from exc

        logger.warning(
            "mcp_http_complete server=%s method=%s elapsed_ms=%d",
            server.server_id,
            method,
            (perf_counter() - started) * 1000,
        )

        if not isinstance(body, Mapping):
            raise MCPToolInvocationError(
                f"MCP server {server.server_id!r} returned a non-object body"
            )

        error = body.get("error")
        if error is not None:
            message = (
                error.get("message")
                if isinstance(error, Mapping)
                else str(error)
            )
            raise MCPToolInvocationError(
                f"MCP tool call to {server.server_id!r} failed: {message}"
            )

        result = body.get("result")
        if not isinstance(result, Mapping):
            raise MCPToolInvocationError(
                f"MCP server {server.server_id!r} returned no result"
            )
        return dict(result)
