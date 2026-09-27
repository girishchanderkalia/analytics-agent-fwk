"""Authored markdown packages translate to the framework's normalized form."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

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

AGENT = ROOT / "agents" / "opo-monitoring"


@pytest.fixture(scope="module")
def definition():
    return translate_markdown_agent(AGENT)


def node(definition, node_id):
    return next(
        item for item in definition.graph.nodes if item.node_id == node_id
    )


def test_identity_and_entry_come_from_the_package(definition) -> None:
    assert definition.agent_id == "opo-monitoring-agent"
    assert definition.version == "1.0"
    assert definition.graph.entry_node == "parse_trend_request"


def test_authored_node_types_map_to_framework_kinds(definition) -> None:
    kinds = {item.node_id: item.kind for item in definition.graph.nodes}

    assert kinds["parse_trend_request"] == "model"
    assert kinds["read_trends"] == "tool"
    assert kinds["analyse_trends"] == "tool"
    assert kinds["approve_investigation"] == "interrupt"


def test_model_nodes_carry_prompt_contract_and_result(definition) -> None:
    config = node(definition, "parse_trend_request").config

    assert config["prompt"] == "trend_filters"
    assert config["output_contract"] == "TrendFilters"
    assert config["result_key"] == "trend_filters"


def test_capability_nodes_bind_to_declared_mcp_tools(definition) -> None:
    config = node(definition, "read_trends").config

    assert (config["server"], config["tool"]) == (
        "analytics-foundation",
        "query_trends",
    )
    assert config["arguments"]["days"] == "$.trend_filters.lookback_days"
    assert config["arguments"]["lot_ids"] == "$.trend_filters.lot_ids"


def test_operation_nodes_bind_to_the_application_capability_server(
    definition,
) -> None:
    config = node(definition, "analyse_trends").config

    assert (config["server"], config["tool"]) == (
        "opo-capability",
        "analyze_trends",
    )
    assert config["arguments"]["series"] == "$.trend_series"


def test_scattered_results_become_a_transform_node(definition) -> None:
    assignments = node(definition, "read_trends__map").config["assignments"]

    assert assignments == {
        "trend_series": "$.read_trends__result.series",
        "read_trends__result": None,
    }
    assert any(
        edge.source == "read_trends" and edge.target == "read_trends__map"
        for edge in definition.graph.edges
    )


def test_tool_results_are_declared_state(definition) -> None:
    properties = definition.state.schema["properties"]

    assert "read_trends__result" in properties


def test_downstream_edges_start_from_the_mapping_node(definition) -> None:
    targets = {
        edge.target
        for edge in definition.graph.edges
        if edge.source == "read_trends__map"
    }

    assert targets == {"review_trends", "interpret_detection_scope"}


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
        "trend_filters",
        "detection_scope",
        "findings_summary",
    }
    assert "Application-owned knowledge" in definition.knowledge[0]


def test_declared_tools_are_deduplicated(definition) -> None:
    identities = {
        (tool.server, tool.name) for tool in definition.tools
    }

    assert ("opo-capability", "analyze_trends") in identities
    assert ("analytics-foundation", "query_wafers") in identities
    assert len(identities) == len(definition.tools)


def test_contracts_stay_available_for_the_contract_provider(definition) -> None:
    assert set(definition.metadata["models"]) == {
        "TrendFilters",
        "DetectionScope",
        "FindingsSummary",
    }


def test_undeclared_capability_reference_is_rejected(tmp_path) -> None:
    import shutil

    target = tmp_path / "agent"
    shutil.copytree(AGENT, target)
    workflow = target / "workflow-definition.md"
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(
            "capability: data_query.read_trends",
            "capability: data_query.missing",
        ),
        encoding="utf-8",
    )

    # Package validation rejects this before translation is reached.
    with pytest.raises(ValueError, match="undeclared"):
        translate_markdown_agent(target)
