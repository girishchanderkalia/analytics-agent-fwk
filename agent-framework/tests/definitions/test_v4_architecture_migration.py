from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "agent-framework" / "agent-runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from definitions import translate_markdown_agent
from bootstrap.markdown_agent_registration import register_markdown_agents
from mcp_tools.fixed_registry import create_fixed_tool_registry


V4 = ROOT / "agents" / "opo-analysis-agent-v4"
PACKAGES = (
    ROOT / "agents" / "opo-analysis-agent-v1",
    V4,
)


def test_all_opo_packages_load_with_governed_tools_only():
    expected = {
        "opo-analysis-agent-v1": "V1",
        "opo-analysis-agent-v4": "V4",
    }

    for package in PACKAGES:
        definition = translate_markdown_agent(package)
        assert definition.agent_id in expected
        assert definition.version == expected[definition.agent_id]
        assert {tool.server for tool in definition.tools} == {"analytics-foundation"}
        assert all(tool.name in {
            "query_trends", "query_trend_series", "get_distribution_stats", "detect_outliers", "get_metadata",
            "create_workspace", "add_workspace_filters",
            "register_dataset", "query_wafers", "run_tdbb", "getWaferLevelKpis", "summarize_tdbb_evidence",
        } for tool in definition.tools)

        registry = create_fixed_tool_registry()
        for tool in definition.tools:
            assert registry.resolve(tool).key.server == tool.server


def test_all_opo_packages_register_as_distinct_versions():
    catalog, result = register_markdown_agents(
        application_id="opo-monitoring",
        package_roots=list(PACKAGES),
    )

    assert len(result.registrations) == 2
    assert {record.key.agent_id for record in result.registrations} == {
        "opo-analysis-agent-v1", "opo-analysis-agent-v4",
    }
    assert len(catalog.list_for_application("opo-monitoring")) == 2


def test_v4_reads_trends_from_lanadb_and_tdbb_from_foundation():
    definition = translate_markdown_agent(V4)
    nodes = {node.node_id: node for node in definition.graph.nodes}

    assert {(tool.server, tool.name) for tool in definition.tools} == {
        ("analytics-foundation", "getWaferLevelKpis"),
        ("analytics-foundation", "run_tdbb"),
        ("analytics-foundation", "summarize_tdbb_evidence"),
    }
    assert "read_trends" not in nodes
    assert "compare_tdbb" not in nodes
    assert nodes["request_trend_evidence"].kind == "tool"
    assert nodes["request_trend_evidence"].config["server"] == "analytics-foundation"
    assert nodes["request_trend_evidence"].config["arguments"] == {
        "lotExposureStartFrom": "$.trend_filters.start_date",
        "lotExposureStartTo": "$.trend_filters.end_date",
        "productIds": "$.trend_filters.product_ids",
        "layerIds": "$.trend_filters.layer_ids",
        "exposureEquipmentIds": "$.trend_filters.exposure_equipment_ids",
        "lotIds": "$.trend_filters.lot_ids",
        "chuckIds": "$.trend_filters.chuck_ids",
    }
    assert nodes["request_trend_evidence__map"].config["assignments"] == {
        "trend_rows": "$.request_trend_evidence__result.rows",
        "trend_rows_truncated": "$.request_trend_evidence__result.truncated",
        "request_trend_evidence__result": None,
    }
    assert nodes["suggest_change"].config["input_projection"]["trend_rows"] == {
        "compact_list": "$.trend_rows",
        "fields": ["lotStart", "chuckId", "kpiValue1", "kpiValue2"],
    }
    assert nodes["request_tdbb_before"].kind == "tool"
    assert nodes["request_tdbb_after"].kind == "tool"
    assert nodes["request_tdbb_before__map"].config["assignments"] == {
        "tdbb_before_run": "$.request_tdbb_before__result",
        "request_tdbb_before__result": None,
    }
    assert nodes["request_tdbb_after__map"].config["assignments"] == {
        "tdbb_after_run": "$.request_tdbb_after__result",
        "request_tdbb_after__result": None,
    }


def test_default_startup_has_three_deployables_and_v4_only():
    startup = (ROOT / "scripts" / "start-services.sh").read_text(encoding="utf-8")
    local_deploy = (ROOT / "scripts" / "local-deploy.sh").read_text(encoding="utf-8")

    assert "start_service \"opo-capability\"" not in startup
    assert "OPO_CAPABILITY_MCP_URL" not in startup
    for package in ("opo-analysis-agent-v1", "opo-analysis-agent-v4"):
        assert f"agents/{package}" in startup
        assert f"agents/{package}" in local_deploy
    assert "agents/opo-analysis-agent-v5" not in startup
    assert "agents/opo-analysis-agent-v5" not in local_deploy


def test_v4_backend_switch_changes_only_tool(tmp_path):
    original = translate_markdown_agent(V4)
    package = tmp_path / "mock-v4"
    shutil.copytree(V4, package)
    document = package / "agent.md"
    document.write_text(document.read_text(encoding="utf-8").replace(
        "tool: getWaferLevelKpis", "tool: query_trends"), encoding="utf-8")
    switched = translate_markdown_agent(package)
    registry = create_fixed_tool_registry()
    for tool in switched.tools:
        registry.resolve(tool)
    for before, after in zip(original.graph.nodes, switched.graph.nodes):
        assert before.node_id == after.node_id and before.kind == after.kind
        if before.node_id == "request_trend_evidence":
            assert {**before.config, "tool": "query_trends"} == after.config
        else:
            assert before.config == after.config


def test_v4_exact_example_prompt_cannot_be_restricted_to_one_chuck():
    from execution.output_rules import normalize_output

    definition = translate_markdown_agent(V4)
    nodes = {node.node_id: node for node in definition.graph.nodes}
    rules = nodes["parse_trend_request"].config["guardrails"]["rules"]
    prompt = "Show OPO performance of product AAA2, layer OV_NO_ID2 on scanner GW021 since 17 Aug."
    wrong = {"chuck_ids": ["Waferstage chuck ID 1"], "product_ids": ["AAA2"],
             "layer_ids": ["OV_NO_ID2"], "exposure_equipment_ids": ["GW021"]}
    corrected = normalize_output(wrong, rules, {"question": prompt})
    assert corrected == {**wrong, "chuck_ids": []}
    explicit = normalize_output(wrong, rules, {"question": prompt + " Use chuck 2."})
    assert explicit["chuck_ids"] == ["Waferstage chuck ID 2"]


def test_v4_reports_use_the_deterministic_tool_and_preserve_public_fields():
    definition = translate_markdown_agent(V4)
    nodes = {node.node_id: node for node in definition.graph.nodes}
    cases = (("analyze_tdbb", "overview", "tdbb_model_analysis"),
             ("summarize_tdbb", "summary", "tdbb_summary"),
             ("analyze_nce_root_cause", "nce", "nce_root_cause_analysis"))
    for name, section, target in cases:
        assert nodes[name].kind == "tool"
        assert nodes[name].config["tool"] == "summarize_tdbb_evidence"
        assert nodes[name].config["arguments"] == {
            "before_periods": "$.tdbb_before_run.periods", "after_periods": "$.tdbb_after_run.periods",
            "section": section,
        }
        assert nodes[name + "__map"].config["assignments"] == {
            target: "$." + name + "__result", name + "__result": None,
        }