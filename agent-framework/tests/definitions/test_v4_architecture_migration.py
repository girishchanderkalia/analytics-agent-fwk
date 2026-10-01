from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "agent-framework" / "agent-runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from definitions import translate_markdown_agent
from bootstrap.markdown_agent_registration import register_markdown_agents
from mcp_tools.fixed_registry import create_fixed_tool_registry


V4 = ROOT / "agents" / "opo-monitoring-v4"
PACKAGES = (
    ROOT / "agents" / "opo-monitoring",
    ROOT / "agents" / "opo-monitoring-v2",
    ROOT / "agents" / "opo-monitoring-v3",
    V4,
)


def test_all_opo_packages_load_with_foundation_only_tools():
    expected = {
        "opo-monitoring-agent": "1.0",
        "opo-monitoring-v2": "2.0",
        "opo-monitoring-v3": "3.0",
        "opo-monitoring-v4": "4.0",
    }

    for package in PACKAGES:
        definition = translate_markdown_agent(package)
        assert definition.agent_id in expected
        assert definition.version == expected[definition.agent_id]
        assert {tool.server for tool in definition.tools} == {"analytics-foundation"}
        assert all(tool.name in {
            "query_trends", "get_distribution_stats", "get_metadata",
            "create_workspace", "add_workspace_filters",
            "register_dataset", "query_wafers", "run_tdbb",
        } for tool in definition.tools)

        registry = create_fixed_tool_registry()
        for tool in definition.tools:
            assert registry.resolve(tool).key.server == "analytics-foundation"


def test_all_opo_packages_register_as_distinct_versions():
    catalog, result = register_markdown_agents(
        application_id="opo-monitoring",
        package_roots=list(PACKAGES),
    )

    assert len(result.registrations) == 4
    assert {record.key.agent_id for record in result.registrations} == {
        "opo-monitoring-agent", "opo-monitoring-v2", "opo-monitoring-v3",
        "opo-monitoring-v4",
    }
    assert len(catalog.list_for_application("opo-monitoring")) == 4


def test_v4_uses_model_mediated_foundation_tools_only():
    definition = translate_markdown_agent(V4)
    nodes = {node.node_id: node for node in definition.graph.nodes}

    assert {tool.server for tool in definition.tools} == {"analytics-foundation"}
    assert {tool.name for tool in definition.tools} == {"query_trends", "run_tdbb"}
    assert "read_trends" not in nodes
    assert "compare_tdbb" not in nodes
    assert nodes["request_trend_evidence"].config["tool_results_to"] == "trend_series"
    assert nodes["request_tdbb_before"].config["tool_results_to"] == "tdbb_before_run"
    assert nodes["request_tdbb_before"].config["require_tool_call"] is True
    assert nodes["request_tdbb_after"].config["tool_results_to"] == "tdbb_after_run"
    assert nodes["request_tdbb_after"].config["require_tool_call"] is True
    assert nodes["request_tdbb_before"].config["approval_state"] == "comparison_requested"
    assert nodes["request_tdbb_after"].config["approval_state"] == "comparison_requested"


def test_default_startup_has_three_deployables_and_v4_only():
    startup = (ROOT / "scripts" / "start-services.sh").read_text(encoding="utf-8")
    local_deploy = (ROOT / "scripts" / "local-deploy.sh").read_text(encoding="utf-8")

    assert "start_service \"opo-capability\"" not in startup
    assert "OPO_CAPABILITY_MCP_URL" not in startup
    for package in ("opo-monitoring", "opo-monitoring-v2", "opo-monitoring-v3", "opo-monitoring-v4"):
        assert f"agents/{package}" in startup
        assert f"agents/{package}" in local_deploy