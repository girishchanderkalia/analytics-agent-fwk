"""Operation nodes dispatch to framework-registered MCP tools."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
AGENT_RUNTIME = ROOT / "agent-framework" / "agent-runtime"
if str(AGENT_RUNTIME) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME))

from mcp_tools.client import MCPToolResult  # noqa: E402
from mcp_tools.errors import MCPServerNotFoundError  # noqa: E402
from mcp_tools.models import MCPServerRegistration  # noqa: E402
from mcp_tools.operation_dispatch import (  # noqa: E402
    McpOperationDispatchError,
    McpOperationRegistry,
    load_operation_declarations,
)
from mcp_tools.server_registry import (  # noqa: E402
    environment_variable_for,
    registrations_from_environment,
)

SERVER = MCPServerRegistration(
    server_id="opo-capability",
    display_name="opo-capability",
    transport="http",
    endpoint="http://127.0.0.1:8300/mcp",
)

DECLARATION = {
    "analyse_trends": {
        "id": "analyse_trends",
        "server": "opo-capability",
        "tool": "analyze_trends",
        "request": {
            "series": "${state.trend_series}",
            "mode": "${state.detection_scope.mode}",
        },
        "result": {
            "analysis": "${result.analysis}",
            "outliers": "${result.outliers}",
        },
    }
}


class RecordingClient:
    def __init__(self, structured=None, is_error=False):
        self.structured = structured or {"analysis": [], "outliers": []}
        self.is_error = is_error
        self.calls = []

    def call_tool(self, *, server, tool_name, arguments):
        self.calls.append((server.server_id, tool_name, arguments))
        return MCPToolResult(
            structured_content=self.structured,
            is_error=self.is_error,
        )


def registry(client) -> McpOperationRegistry:
    return McpOperationRegistry(DECLARATION, {"opo-capability": SERVER}, client)


def test_state_is_mapped_onto_the_declared_tool_arguments() -> None:
    client = RecordingClient({"analysis": [{"id": "a"}], "outliers": []})

    updates = registry(client).invoke(
        "analyse_trends",
        {"trend_series": [{"machine": "M1"}], "detection_scope": {"mode": "baseline"}},
    )

    server_id, tool_name, arguments = client.calls[0]
    assert (server_id, tool_name) == ("opo-capability", "analyze_trends")
    assert arguments == {"series": [{"machine": "M1"}], "mode": "baseline"}
    assert updates == {"analysis": [{"id": "a"}], "outliers": []}


def test_undeclared_operation_is_rejected() -> None:
    with pytest.raises(McpOperationDispatchError, match="not declared"):
        registry(RecordingClient()).invoke("unknown", {})


def test_unregistered_server_is_rejected() -> None:
    value = McpOperationRegistry(DECLARATION, {}, RecordingClient())

    with pytest.raises(MCPServerNotFoundError, match="opo-capability"):
        value.invoke(
            "analyse_trends",
            {"trend_series": [], "detection_scope": {"mode": "baseline"}},
        )


def test_tool_error_is_surfaced() -> None:
    client = RecordingClient(is_error=True)

    with pytest.raises(McpOperationDispatchError, match="reported an error"):
        registry(client).invoke(
            "analyse_trends",
            {"trend_series": [], "detection_scope": {"mode": "baseline"}},
        )


def test_endpoints_come_from_deployment_configuration() -> None:
    assert environment_variable_for("opo-capability") == "OPO_CAPABILITY_MCP_URL"

    registrations = registrations_from_environment(
        ["opo-capability"],
        {"OPO_CAPABILITY_MCP_URL": "http://127.0.0.1:8300/mcp"},
    )

    assert registrations["opo-capability"].endpoint == "http://127.0.0.1:8300/mcp"


def test_missing_endpoint_names_the_variable() -> None:
    with pytest.raises(MCPServerNotFoundError, match="OPO_CAPABILITY_MCP_URL"):
        registrations_from_environment(["opo-capability"], {})


def test_declarations_load_from_the_agent_package() -> None:
    from execution.definition_loader import AgentRepository

    bundle = AgentRepository(ROOT / "agents").load("opo-monitoring")
    declarations = load_operation_declarations(bundle)

    assert "analyse_trends" in declarations
    assert declarations["analyse_trends"]["server"] == "opo-capability"
    assert declarations["analyse_trends"]["tool"] == "analyze_trends"


def test_every_workflow_operation_node_is_declared() -> None:
    from execution.definition_loader import AgentRepository

    bundle = AgentRepository(ROOT / "agents").load("opo-monitoring")
    declared = set(load_operation_declarations(bundle))
    nodes = {
        node["operation"]
        for node in bundle.workflow.metadata["nodes"]
        if node.get("type") == "operation"
    }

    assert nodes <= declared
