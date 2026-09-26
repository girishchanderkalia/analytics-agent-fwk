from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest


V3_ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"
AGENT_REPOSITORY_ROOT = V3_ROOT / "agents"
OPO_AGENT_ROOT = AGENT_REPOSITORY_ROOT / "opo-monitoring"

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
    assert bundle.agent_id == "opo-monitoring-agent"
    assert bundle.version == "1.0"
    assert bundle.display_name == "OPO Monitoring Agent"


def test_all_required_definition_files_are_loaded() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert set(bundle.definitions) == set(REQUIRED_DEFINITIONS)


def test_agent_definition_is_available() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert bundle.agent.kind == "agent"
    assert bundle.agent.id == "opo-monitoring-agent"


def test_workflow_definition_is_available() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert bundle.workflow.kind == "workflow"
    assert bundle.workflow.id == "opo-monitoring-workflow"


def test_state_definition_is_available() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert bundle.state.kind == "state-model"
    assert bundle.state.id == "opo-monitoring-state"


def test_capability_definition_is_available() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert bundle.capabilities.kind == "tools-and-capabilities"
    assert bundle.capabilities.id == "opo-monitoring-capabilities"


def test_knowledge_definition_is_available() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert bundle.knowledge.kind == "knowledge-model"
    assert bundle.knowledge.id == "opo-monitoring-knowledge"


def test_sequence_definition_is_available() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    assert bundle.sequences.kind == "sequence-diagrams"
    assert bundle.sequences.id == "opo-monitoring-sequences"


def test_repository_discovers_opo_monitoring() -> None:
    repository = AgentRepository(AGENT_REPOSITORY_ROOT)

    discovered_agents = repository.list_agent_directories()

    assert "opo-monitoring" in discovered_agents


def test_repository_loads_agent_by_directory_name() -> None:
    repository = AgentRepository(AGENT_REPOSITORY_ROOT)

    bundle = repository.load("opo-monitoring")

    assert bundle.agent_id == "opo-monitoring-agent"


def test_repository_loads_all_agents_by_agent_id() -> None:
    repository = AgentRepository(AGENT_REPOSITORY_ROOT)

    agents = repository.load_all()

    assert "opo-monitoring-agent" in agents
    assert agents["opo-monitoring-agent"].display_name == (
        "OPO Monitoring Agent"
    )


def test_workflow_uses_supported_node_types() -> None:
    bundle = load_agent_definition(OPO_AGENT_ROOT)

    nodes = bundle.workflow.metadata["nodes"]

    actual_types = {node["type"] for node in nodes}

    assert actual_types <= SUPPORTED_NODE_TYPES
    assert "model" in actual_types
    assert "operation" in actual_types
    assert "capability" in actual_types
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
