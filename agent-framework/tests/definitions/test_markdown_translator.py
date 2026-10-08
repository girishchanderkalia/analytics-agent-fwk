"""Authored markdown packages translate to the framework's normalized form."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
AGENT_RUNTIME = ROOT / "agent-framework" / "agent-runtime"
if str(AGENT_RUNTIME) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME))

from definitions.markdown_translator import (  # noqa: E402
    translate_markdown_agent,
)
from definitions.normalization_errors import (  # noqa: E402
    DefinitionNormalizationError,
)

AGENT = ROOT / "agents" / "opo-analysis-agent-v1"


@pytest.fixture(scope="module")
def definition():
    return translate_markdown_agent(AGENT)


def node(definition, node_id):
    return next(
        item for item in definition.graph.nodes if item.node_id == node_id
    )


def test_identity_and_entry_come_from_the_package(definition) -> None:
    assert definition.agent_id == "opo-analysis-agent-v1"
    assert definition.version == "V1"
    assert definition.graph.entry_node == "parse_trend_request"


def test_authored_node_types_map_to_framework_kinds(definition) -> None:
    kinds = {item.node_id: item.kind for item in definition.graph.nodes}

    assert kinds["parse_trend_request"] == "model"
    assert kinds["request_trend_evidence"] == "tool"
    assert kinds["analyse_trends"] == "tool"
    assert kinds["approve_investigation"] == "interrupt"


def test_model_nodes_carry_prompt_contract_and_result(definition) -> None:
    config = node(definition, "parse_trend_request").config

    assert config["prompt"] == "parse_trend_request"
    assert config["output_contract"] == "parse_trend_request"
    assert config["result_key"] == "trend_filters"


def test_trend_model_binds_to_declared_foundation_tool(definition) -> None:
    config = node(definition, "request_trend_evidence__map").config

    assert config["assignments"] == {
        "trend_series": "$.request_trend_evidence__result.series",
        "request_trend_evidence__result": None,
    }


def test_wafer_preview_uses_highlighted_outlier_scopes(definition) -> None:
    config = node(definition, "preview_wafers").config
    assert config["arguments"]["filters"] == {"outlier_scopes": "$.outliers"}
    assert node(definition, "preview_wafers__map").config["assignments"]["wafer_rows"] == "$.preview_wafers__result.rows"


def test_downstream_edges_start_from_the_mapping_node(definition) -> None:
    targets = {
        edge.target
        for edge in definition.graph.edges
        if edge.source == "request_trend_evidence__map"
    }

    assert targets == {"review_trends", "read_distribution_stats"}


def test_approval_nodes_declare_their_payload(definition) -> None:
    config = node(definition, "approve_investigation").config

    assert config["result_key"] == "investigation_approved"
    assert config["approval_id"] == "investigate_outlier"
    assert config["payload"] == {
        "question": "Investigate the selected outlier?",
        "approve_label": "Investigate",
        "reject_label": "Reject",
        "detected_outliers": "$.outliers",
        "selected_outlier": "$.selected_outlier",
    }


def test_recommended_action_approval_uses_findings_as_options(definition) -> None:
    config = node(definition, "select_next_action").config

    assert config["approval_id"] == "select_recommended_action"
    assert config["result_key"] == "next_action_approved"
    assert config["decision_fields"] == {
        "next_action_approved": "approved",
        "selected_action": "selected_action",
    }
    assert config["payload"]["options"] == "$.findings.recommended_next_actions"


def test_recommended_action_routes_only_the_supported_action(definition) -> None:
    conditioned = {
        (edge.source, edge.target, edge.condition)
        for edge in definition.graph.edges
        if edge.condition is not None
    }

    assert (
        "select_next_action",
        "classify_spatial_pattern",
        'selected_action == "Analyze wafer spatial pattern"',
    ) in conditioned


def test_routing_conditions_become_conditional_edges(definition) -> None:
    conditioned = [
        edge for edge in definition.graph.edges if edge.condition is not None
    ]

    assert ("analyse_trends__map", "summarize_findings", "outliers == []") in {
        (edge.source, edge.target, edge.condition) for edge in conditioned
    }


def test_terminal_edges_use_the_reserved_end_target(definition) -> None:
    assert any(edge.target == "END" for edge in definition.graph.edges)


def test_state_model_becomes_a_json_schema(definition) -> None:
    properties = definition.state.schema["properties"]

    assert definition.state.schema["type"] == "object"
    assert properties["question"]["type"] == "string"
    assert properties["outliers"] == {
        "type": "array",
        "items": {"type": "object"},
        "default": [],
        "description": "Candidate outliers identified by trend analysis.",
    }
    assert properties["cancelled_at"]["type"] == ["string", "null"]


def test_prompts_and_knowledge_are_carried_through(definition) -> None:
    assert {prompt.prompt_id for prompt in definition.prompts} == {
        "parse_trend_request", "interpret_detection_scope",
        "classify_spatial_pattern", "summarize_findings",
    }
    assert "Runtime information is operational context" in definition.knowledge[0]


def test_v1_domain_topics_are_explicitly_scoped(definition) -> None:
    from bootstrap.langgraph_dependencies import PackagePromptProvider

    provider = PackagePromptProvider(definition)
    trend = provider.render("parse_trend_request", {})
    detection = provider.render("interpret_detection_scope", {})
    spatial = provider.render("classify_spatial_pattern", {})
    findings = provider.render("summarize_findings", {})

    assert "Domain knowledge (trends)" in trend
    assert "Domain knowledge (outliers)" not in trend
    assert "Domain knowledge (wafers)" not in trend
    assert "Domain knowledge (outliers)" in detection
    assert "Zero samples mean missing distribution evidence" in detection
    assert "Domain knowledge (wafers)" in spatial
    assert "Wafer records identified as anomalous" in spatial
    for topic in ("trends", "outliers", "wafers"):
        assert f"Domain knowledge ({topic})" in findings
    for prompt in (trend, detection, spatial, findings):
        assert "High confidence requires" in prompt


def test_v1_filter_scope_is_owned_by_the_agent(definition) -> None:
    from execution.output_rules import check_output
    from langgraph_runtime.node_library import _model_input

    config = node(definition, "parse_trend_request").config
    state = {
        "question": "show outliers",
        "conversation_context": {
            "current_date": "2026-10-08",
            "available_trend_scopes": [{"product": "Product4", "layer": "L4"}],
            "selected_product_ids": ["Product4"],
        },
        "trend_series": [{"product": "Product4"}],
    }
    model_input = _model_input(config, state)
    assert "show outliers" in model_input
    assert "2026-10-08" in model_input
    assert "Product4" not in model_input
    assert "available_trend_scopes" not in model_input
    rules = config["guardrails"]["rules"]
    assert config["guardrails"]["on_failure"] == "stop"
    assert check_output({"product_ids": ["Product4"]}, rules, state)
    assert not check_output({"product_ids": [], "layer_ids": []}, rules, state)
    assert not check_output(
        {"product_ids": ["AAA2"], "layer_ids": ["OV_NO_ID2"]},
        rules,
        {"question": "show outliers for product AAA2 on layer OV_NO_ID2"},
    )


def test_declared_tools_are_deduplicated(definition) -> None:
    identities = {
        (tool.server, tool.name) for tool in definition.tools
    }

    assert ("analytics-foundation", "query_wafers") in identities
    assert all(server == "analytics-foundation" for server, _ in identities)
    assert len(identities) == len(definition.tools)


def test_contracts_stay_available_for_the_contract_provider(definition) -> None:
    assert set(definition.metadata["models"]) == {
        "parse_trend_request", "interpret_detection_scope",
        "classify_spatial_pattern", "summarize_findings",
    }


def test_invalid_inline_capability_is_rejected(tmp_path) -> None:
    import shutil
    from execution.definition_loader import split_front_matter

    target = tmp_path / "agent"
    shutil.copytree(AGENT, target)
    workflow = target / "agent.md"
    metadata, markdown = split_front_matter(workflow)
    metadata["steps"][1]["capability"] = "missing"
    workflow.write_text(
        "---\n" + yaml.safe_dump(metadata) + "---\n" + markdown,
        encoding="utf-8",
    )

    # Package validation rejects this before translation is reached.
    with pytest.raises(ValueError, match="capability must be a mapping"):
        translate_markdown_agent(target)
