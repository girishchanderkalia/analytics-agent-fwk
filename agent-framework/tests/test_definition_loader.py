from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest


V3_ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"
AGENT_REPOSITORY_ROOT = V3_ROOT / "agents"
OPO_AGENT_ROOT = AGENT_REPOSITORY_ROOT / "opo-analysis-agent-v1"

# Add agent-runtime to Python's module search path.
# This must appear before importing execution.definition_loader.
agent_runtime_path = str(AGENT_RUNTIME_ROOT)

if agent_runtime_path not in sys.path:
    sys.path.insert(0, agent_runtime_path)


from execution.definition_loader import (  # noqa: E402
    AgentDefinitionBundle,
    AgentDefinitionError,
    AgentRepository,
    REQUIRED_DEFINITIONS,
    SUPPORTED_NODE_TYPES,
    load_agent_definition,
)


def test_opo_agent_bundle_loads() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert isinstance(bundle, AgentDefinitionBundle)
    assert bundle.agent_id == "opo-analysis-agent-v1"
    assert bundle.version == "V1"
    assert bundle.display_name == "OPO Analysis Agent"


def test_single_file_v4_loads_and_derives_state() -> None:
    bundle = load_agent_definition(AGENT_REPOSITORY_ROOT / "opo-analysis-agent-v4")

    assert bundle.agent_id == "opo-analysis-agent-v4"
    assert bundle.version == "V4"
    assert bundle.workflow.metadata["entry_node"] == "parse_trend_request"
    fields = bundle.state.metadata["fields"]
    assert fields["trend_series"]["type"] == "object_list"
    assert fields["comparison_requested"]["type"] == "boolean"
    assert "tdbb_before_run" in fields
    assert "detection_scope" not in fields
    assert len(bundle.agent.metadata["models"]) == 6
    assert len(bundle.capabilities.metadata["capabilities"]) == 2


def test_template_loads_but_is_not_discovered() -> None:
    repository = AgentRepository(AGENT_REPOSITORY_ROOT)
    bundle = load_agent_definition(AGENT_REPOSITORY_ROOT / "template")

    assert bundle.agent_id == "example-domain-agent"
    assert bundle.capabilities.metadata["capabilities"] == []
    assert "template" not in repository.list_agent_directories()
    assert not repository.contains("template")
    assert repository.contains("opo-analysis-agent-v4")
    assert not repository.contains("opo-analysis-agent-v5")


def test_single_file_knowledge_is_explicitly_scoped() -> None:
    from bootstrap.langgraph_dependencies import PackagePromptProvider
    from definitions.markdown_translator import translate_markdown_agent

    definition = translate_markdown_agent(AGENT_REPOSITORY_ROOT / "opo-analysis-agent-v4")
    provider = PackagePromptProvider(definition)
    trend = provider.render("parse_trend_request", {})
    tdbb = provider.render("analyze_tdbb", {})
    radial = provider.render("analyze_nce_root_cause", {})

    assert "Runtime status and conversation metadata" in trend
    assert "Domain knowledge (overlay)" in trend
    assert "Domain knowledge (tdbb)" not in trend
    assert "Domain knowledge (tdbb)" in tdbb
    assert "Domain knowledge (nce_radial)" not in tdbb
    assert "Domain knowledge (nce_radial)" in radial
    assert "Foundation before-period TDBB result" in radial


def test_single_file_v4_preserves_workflow_and_application_contracts() -> None:
    from definitions.markdown_translator import translate_markdown_agent

    definition = translate_markdown_agent(AGENT_REPOSITORY_ROOT / "opo-analysis-agent-v4")
    nodes = {node.node_id: node for node in definition.graph.nodes}
    assert len(nodes) == 13
    assert len(definition.graph.edges) == 17
    assert nodes["request_comparison"].config["approval_id"] == "request_tdbb_comparison"
    assert nodes["request_comparison"].config["decision_fields"] == {
        "comparison_requested": "approved", "comparison_request": "comparison_request",
    }
    assert nodes["review_tdbb"].config["approval_id"] == "review_tdbb_results"
    assert nodes["review_tdbb"].config["decision_fields"] == {
        "tdbb_explanation_requested": "approved",
        "root_cause_requested": "approved",
        "root_cause_request": "root_cause_request",
    }
    assert nodes["request_tdbb_before"].config["arguments"]["end_date"] == "$.comparison_scope.change_date"
    assert nodes["request_tdbb_after"].config["arguments"]["end_date"] == "$.trend_filters.end_date"


def test_single_file_unknown_knowledge_topic_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "agent"
    shutil.copytree(AGENT_REPOSITORY_ROOT / "template", target)
    document = target / "agent.md"
    document.write_text(
        document.read_text(encoding="utf-8").replace(
            "knowledge: [observations]", "knowledge: [unknown_topic]"
        ),
        encoding="utf-8",
    )
    with pytest.raises(AgentDefinitionError, match="unknown knowledge topics"):
        load_agent_definition(target)


def test_single_file_prompt_preview(capsys) -> None:
    from execution.definition_loader import main

    assert main([
        str(AGENT_REPOSITORY_ROOT / "opo-analysis-agent-v4"),
        "--preview-step", "analyze_nce_root_cause",
    ]) == 0
    output = capsys.readouterr().out
    assert "Domain knowledge (nce_radial)" in output
    assert "Application knowledge:" in output
    assert "Data semantics:" in output
    assert "$.tdbb_before_run.periods" in output
    assert "correlated_evidence" in output
    assert main([
        str(AGENT_REPOSITORY_ROOT / "template"), "--preview-step", "unknown",
    ]) == 1


def test_all_required_definition_files_are_loaded() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert set(bundle.definitions) == set(REQUIRED_DEFINITIONS)


def test_agent_definition_is_available() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert bundle.agent.kind == "agent"
    assert bundle.agent.id == "opo-analysis-agent-v1"


def test_workflow_definition_is_available() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert bundle.workflow.kind == "workflow"
    assert bundle.workflow.id == "opo-analysis-agent-v1-workflow"


def test_state_definition_is_available() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert bundle.state.kind == "state-model"
    assert bundle.state.id == "opo-analysis-agent-v1-state"


def test_capability_definition_is_available() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert bundle.capabilities.kind == "tools-and-capabilities"
    assert bundle.capabilities.id == "opo-analysis-agent-v1-capabilities"


def test_knowledge_definition_is_available() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert bundle.knowledge.kind == "knowledge-model"
    assert bundle.knowledge.id == "opo-analysis-agent-v1-knowledge"


def test_sequence_definition_is_available() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert bundle.sequences.kind == "sequence-diagrams"
    assert bundle.sequences.id == "opo-analysis-agent-v1-sequences"


def test_repository_discovers_opo_monitoring() -> None:
    repository = AgentRepository(AGENT_REPOSITORY_ROOT)

    discovered_agents = repository.list_agent_directories()

    assert "opo-analysis-agent-v1" in discovered_agents


def test_repository_loads_agent_by_directory_name() -> None:
    repository = AgentRepository(AGENT_REPOSITORY_ROOT)

    bundle = repository.load("opo-analysis-agent-v1")

    assert bundle.agent_id == "opo-analysis-agent-v1"


def test_repository_loads_all_agents_by_agent_id() -> None:
    repository = AgentRepository(AGENT_REPOSITORY_ROOT)

    agents = repository.load_all()

    assert "opo-analysis-agent-v1" in agents
    assert agents["opo-analysis-agent-v1"].display_name == "OPO Analysis Agent"


def test_workflow_uses_supported_node_types() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    nodes = bundle.workflow.metadata["nodes"]

    actual_types = {node["type"] for node in nodes}

    assert actual_types <= SUPPORTED_NODE_TYPES
    assert "model" in actual_types
    assert actual_types == {"model", "approval", "capability"}
    assert "approval" in actual_types


def test_workflow_entry_node_exists() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    workflow = bundle.workflow.metadata
    node_ids = {node["id"] for node in workflow["nodes"]}

    assert workflow["entry_node"] in node_ids


def test_workflow_capabilities_are_declared() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    declared_capabilities = {
        capability["id"]
        for capability in bundle.capabilities.metadata["capabilities"]
    }

    workflow_capabilities = {
        node["capability"]
        for node in bundle.workflow.metadata["nodes"]
        if node["type"] == "capability"
    }

    assert workflow_capabilities <= declared_capabilities


def test_workflow_model_prompts_are_declared() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    declared_prompts = set(bundle.agent.metadata["prompts"])

    referenced_prompts = {
        node["prompt"]
        for node in bundle.workflow.metadata["nodes"]
        if node["type"] == "model"
    }

    assert referenced_prompts <= declared_prompts


def test_workflow_model_outputs_are_declared() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    declared_models = set(bundle.agent.metadata["models"])

    referenced_outputs = {
        node["output"]
        for node in bundle.workflow.metadata["nodes"]
        if node["type"] == "model"
    }

    assert referenced_outputs <= declared_models


def test_missing_agent_directory_is_rejected(
    tmp_path: Path,
) -> None:
    missing_directory = tmp_path / "missing-agent"

    with pytest.raises(
        AgentDefinitionError,
        match="does not exist",
    ):
        load_agent_definition(missing_directory)


def test_missing_definition_files_are_rejected(
    tmp_path: Path,
) -> None:
    agent_directory = tmp_path / "test-agent"
    agent_directory.mkdir()

    with pytest.raises(
        AgentDefinitionError,
        match="Required definition file is missing",
    ):
        load_agent_definition(agent_directory)


def test_missing_definition_file_is_rejected(
    tmp_path: Path,
) -> None:
    agent_directory = tmp_path / "opo-monitoring"
    shutil.copytree(OPO_AGENT_ROOT, agent_directory)

    missing_file = agent_directory / "workflow-definition.md"
    missing_file.unlink()

    with pytest.raises(
        AgentDefinitionError,
        match=r"Required definition file is missing:.*workflow-definition\.md",
    ):
        load_agent_definition(agent_directory)


def test_unknown_edge_source_is_rejected(
    tmp_path: Path,
) -> None:
    target_agent = tmp_path / "opo-monitoring"
    shutil.copytree(OPO_AGENT_ROOT, target_agent)

    workflow_path = target_agent / "workflow-definition.md"

    content = workflow_path.read_text(encoding="utf-8")
    content = content.replace(
        "from: parse_trend_request",
        "from: unknown_node",
        1,
    )
    workflow_path.write_text(content, encoding="utf-8")

    with pytest.raises(
        AgentDefinitionError,
        match=r"unknown source node",
    ):
        load_agent_definition(target_agent)


def test_unknown_edge_destination_is_rejected(
    tmp_path: Path,
) -> None:
    target_agent = tmp_path / "opo-monitoring"
    shutil.copytree(OPO_AGENT_ROOT, target_agent)

    workflow_path = target_agent / "workflow-definition.md"

    content = workflow_path.read_text(encoding="utf-8")
    content = content.replace(
        "to: interpret_detection_scope",
        "to: unknown_node",
        1,
    )
    workflow_path.write_text(content, encoding="utf-8")

    with pytest.raises(
        AgentDefinitionError,
        match=r"unknown target node",
    ):
        load_agent_definition(target_agent)


def test_end_is_allowed_as_destination() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    edges_to_end = [
        edge
        for edge in bundle.workflow.metadata["edges"]
        if edge["to"] == "END"
    ]

    assert edges_to_end
