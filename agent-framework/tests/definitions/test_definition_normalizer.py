from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent-framework" / "agent-runtime"))

from definitions import DefinitionNormalizationError, normalize_agent_package


def create_package(tmp_path: Path) -> Path:
    root = tmp_path / "normalized-agent"
    root.mkdir()
    (root / "agent-package.yaml").write_text(
        '''kind: agent-package
id: example-agent
version: "1.0"
sources:
  graph: graph.yaml
  state: state.yaml
  prompts: prompts.yaml
  tools: tools.yaml
  knowledge:
    - knowledge.md
metadata:
  display_name: Example Agent
''', encoding="utf-8")
    (root / "graph.yaml").write_text(
        '''entry: interpret
nodes:
  - id: interpret
    kind: model
    config:
      prompt: interpret
  - id: retrieve
    kind: tool
    config:
      tool: read_data
edges:
  - from: interpret
    to: retrieve
  - from: retrieve
    to: END
    condition: state.completed == true
''', encoding="utf-8")
    (root / "state.yaml").write_text(
        '''type: object
properties:
  question:
    type: string
  completed:
    type: boolean
''', encoding="utf-8")
    (root / "prompts.yaml").write_text(
        '''prompts:
  interpret:
    template: Interpret the request using supplied context.
    metadata:
      purpose: interpretation
''', encoding="utf-8")
    (root / "tools.yaml").write_text(
        '''tools:
  - name: read_data
    version: "1"
    server: data
''', encoding="utf-8")
    (root / "knowledge.md").write_text(
        "Application-owned domain knowledge.\n",
        encoding="utf-8",
    )
    return root


def test_normalizes_complete_generic_package(tmp_path: Path) -> None:
    result = normalize_agent_package(create_package(tmp_path))
    assert result.agent_id == "example-agent"
    assert result.graph.entry_node == "interpret"
    assert [node.kind for node in result.graph.nodes] == ["model", "tool"]
    assert result.graph.edges[-1].target == "END"
    assert result.tools[0].name == "read_data"
    assert result.prompts[0].prompt_id == "interpret"
    assert result.knowledge == ("Application-owned domain knowledge.\n",)


def test_node_kind_is_not_domain_validated(tmp_path: Path) -> None:
    root = create_package(tmp_path)
    graph = root / "graph.yaml"
    graph.write_text(
        graph.read_text(encoding="utf-8").replace(
            "kind: model",
            "kind: reusable_standard_node",
        ),
        encoding="utf-8",
    )
    result = normalize_agent_package(root)
    assert result.graph.nodes[0].kind == "reusable_standard_node"


def test_unknown_edge_target_is_rejected(tmp_path: Path) -> None:
    root = create_package(tmp_path)
    graph = root / "graph.yaml"
    graph.write_text(
        graph.read_text(encoding="utf-8").replace("to: END", "to: missing"),
        encoding="utf-8",
    )
    with pytest.raises(DefinitionNormalizationError, match="target"):
        normalize_agent_package(root)


def test_duplicate_tool_reference_is_rejected(tmp_path: Path) -> None:
    root = create_package(tmp_path)
    tools = root / "tools.yaml"
    tools.write_text(
        tools.read_text(encoding="utf-8")
        + "  - name: read_data\n    version: \"1\"\n    server: data\n",
        encoding="utf-8",
    )
    with pytest.raises(DefinitionNormalizationError, match="Duplicate"):
        normalize_agent_package(root)


def test_state_schema_must_be_object(tmp_path: Path) -> None:
    root = create_package(tmp_path)
    (root / "state.yaml").write_text("type: array\n", encoding="utf-8")
    with pytest.raises(DefinitionNormalizationError, match="object"):
        normalize_agent_package(root)
