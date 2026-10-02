"""The fixed MCP tool surface this framework exposes to agents.

The framework serves Analytics Foundation, so the governed tool set is known
at build time: there is no discovery and no dynamic registration. A package
that references a tool outside this set fails to compile.
"""

from __future__ import annotations

from .models import McpToolDescriptor, McpToolKey
from .registry import McpToolRegistry

FOUNDATION_SERVER = "analytics-foundation"
CAPABILITY_SERVER = "opo-capability"
VERSION = "1"

OBJECT_SCHEMA: dict[str, object] = {"type": "object"}

# Governed Analytics Foundation operations.
FOUNDATION_TOOLS: tuple[tuple[str, str], ...] = (
    ("query_trends", "Read OPO KPI trend series."),
    ("get_distribution_stats", "Read empirical KPI distribution statistics."),
    ("detect_outliers", "Deterministically find trend points violating a threshold."),
    ("get_metadata", "Read available dataset and table metadata."),
    ("create_workspace", "Create a governed investigation workspace."),
    ("add_workspace_filters", "Apply filters to an investigation workspace."),
    (
        "get_workspace_connection_info",
        "Read opaque workspace connection information.",
    ),
    ("register_dataset", "Register a dataset in a workspace."),
    ("get_registration_status", "Read dataset registration status."),
    ("query_wafers", "Read wafer-level evidence."),
    ("run_tdbb", "Run TDBB processing before and after a change date."),
    ("compare_tdbb_runs", "Compare completed TDBB runs by ID."),
    ("get_tdbb_run", "Read TDBB run metadata."),
    ("get_tdbb_data", "Read TDBB output rows of one run."),
)

def create_fixed_tool_registry() -> McpToolRegistry:
    """Return the registry every agent in this framework resolves against."""

    registry = McpToolRegistry()
    registry.register_many(
        McpToolDescriptor(
            McpToolKey(name, VERSION, server),
            description,
            OBJECT_SCHEMA,
        )
        for server, tools in ((FOUNDATION_SERVER, FOUNDATION_TOOLS),)
        for name, description in tools
    )
    return registry


def fixed_server_ids() -> tuple[str, ...]:
    """Return the MCP servers this framework talks to."""

    return (FOUNDATION_SERVER,)
