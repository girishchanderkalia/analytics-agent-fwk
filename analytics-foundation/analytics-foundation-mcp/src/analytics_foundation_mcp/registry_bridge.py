"""Bridge Foundation MCP tool metadata to the existing generic registry."""

from __future__ import annotations

from collections.abc import Iterable

from .types import FoundationMcpTool


def to_registry_descriptors(
    tools: Iterable[FoundationMcpTool],
    *,
    server: str = "analytics-foundation",
):
    """Create existing runtime descriptors without duplicating registry logic."""
    from mcp_tools.models import McpToolDescriptor, McpToolKey

    return tuple(
        McpToolDescriptor(
            key=McpToolKey(
                name=tool.name,
                version=tool.version,
                server=server,
            ),
            description=tool.description,
            input_schema=tool.input_schema,
            output_schema=tool.output_schema,
            annotations=tool.annotations,
        )
        for tool in tools
    )
