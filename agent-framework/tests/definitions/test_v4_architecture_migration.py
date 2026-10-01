from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "agent-framework" / "agent-runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from definitions import translate_markdown_agent


V4 = ROOT / "agents" / "opo-monitoring-v4"


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
    assert "agents/opo-monitoring-v4" in startup
    assert "agents/opo-monitoring-v4" in local_deploy