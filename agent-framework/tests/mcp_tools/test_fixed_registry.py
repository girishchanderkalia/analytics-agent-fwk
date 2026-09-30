"""The framework exposes one fixed governed tool surface."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
AGENT_RUNTIME = ROOT / "agent-framework" / "agent-runtime"
if str(AGENT_RUNTIME) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME))

from definitions import translate_markdown_agent  # noqa: E402
from mcp_tools import McpToolNotFoundError  # noqa: E402
from mcp_tools.fixed_registry import (  # noqa: E402
    CAPABILITY_SERVER,
    FOUNDATION_SERVER,
    create_fixed_tool_registry,
    fixed_server_ids,
)
from mcp_tools.models import AgentToolReference  # noqa: E402

AGENT = ROOT / "agents" / "opo-monitoring"


def test_registry_is_identical_on_every_call() -> None:
    first = {tool.key for tool in create_fixed_tool_registry().snapshot()}
    second = {tool.key for tool in create_fixed_tool_registry().snapshot()}

    assert first == second


def test_foundation_operations_are_all_exposed() -> None:
    names = {
        tool.key.name
        for tool in create_fixed_tool_registry().snapshot()
        if tool.key.server == FOUNDATION_SERVER
    }

    assert names == {
        "query_trends",
        "get_distribution_stats",
        "get_metadata",
        "create_workspace",
        "add_workspace_filters",
        "get_workspace_connection_info",
        "register_dataset",
        "get_registration_status",
        "query_wafers",
        "run_tdbb",
        "get_tdbb_run",
        "get_tdbb_data",
    }


def test_application_calculations_are_exposed() -> None:
    names = {
        tool.key.name
        for tool in create_fixed_tool_registry().snapshot()
        if tool.key.server == CAPABILITY_SERVER
    }

    assert names == {
        "normalize_trend_window",
        "analyze_trends",
        "normalize_wafer_evidence",
        "classify_spatial_pattern",
        "compare_tdbb_budgets",
        "suggest_change_date",
    }


def test_servers_are_fixed() -> None:
    assert fixed_server_ids() == (FOUNDATION_SERVER, CAPABILITY_SERVER)


def test_a_tool_outside_the_surface_cannot_be_resolved() -> None:
    registry = create_fixed_tool_registry()

    with pytest.raises(McpToolNotFoundError):
        registry.resolve(
            AgentToolReference(name="drop_table", version="1", server=FOUNDATION_SERVER)
        )


def test_every_tool_the_agent_declares_is_in_the_fixed_surface() -> None:
    registry = create_fixed_tool_registry()
    definition = translate_markdown_agent(AGENT)

    for tool in definition.tools:
        assert registry.resolve(tool).key.name == tool.name
