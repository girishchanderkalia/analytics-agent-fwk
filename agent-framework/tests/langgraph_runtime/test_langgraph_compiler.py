from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent-framework" / "agent-runtime"))

from definitions import (
    NormalizedAgentDefinition,
    NormalizedEdge,
    NormalizedGraph,
    NormalizedNode,
    NormalizedState,
)
from langgraph_runtime.compiler_api import (
    GraphCompilerError,
    LangGraphCompiler,
    build_state_schema,
)


class FakeNodeLibrary:
    def create(self, definition):
        async def node(state):
            return {definition.node_id: True}
        return node


class FakeExpressionEngine:
    async def evaluate(self, expression, state):
        return state.get(expression, False)


class FakeBuilder:
    instances = []

    def __init__(self, state_schema):
        self.state_schema = state_schema
        self.nodes = {}
        self.entry = None
        self.edges = []
        self.conditional = []
        self.compile_arguments = None
        type(self).instances.append(self)

    def add_node(self, name, node):
        self.nodes[name] = node

    def set_entry_point(self, name):
        self.entry = name

    def add_edge(self, source, target):
        self.edges.append((source, target))

    def add_conditional_edges(self, source, router, path_map):
        self.conditional.append((source, router, path_map))

    def compile(self, **kwargs):
        self.compile_arguments = kwargs
        return self


@dataclass
class Checkpointer:
    value: str = "checkpoint"


@dataclass
class Store:
    value: str = "store"


def definition(edges):
    return NormalizedAgentDefinition(
        agent_id="example-agent",
        version="1.0",
        graph=NormalizedGraph(
            entry_node="first",
            nodes=(
                NormalizedNode("first", "transform", {}),
                NormalizedNode("second", "transform", {}),
            ),
            edges=tuple(edges),
        ),
        state=NormalizedState(
            schema={
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "completed": {"type": "boolean"},
                },
            }
        ),
    )


def compiler(expression_engine=None):
    FakeBuilder.instances.clear()
    return LangGraphCompiler(
        FakeNodeLibrary(),
        expression_engine=expression_engine,
        state_graph_factory=FakeBuilder,
        end_marker="__END__",
    )


def test_compiles_nodes_entry_and_fixed_edges() -> None:
    result = compiler().compile(
        definition([
            NormalizedEdge("first", "second"),
            NormalizedEdge("second", "END"),
        ])
    )
    assert result.entry == "first"
    assert set(result.nodes) == {"first", "second"}
    assert result.edges == [
        ("first", "second"),
        ("second", "__END__"),
    ]


def test_compiles_conditioned_edges_with_default() -> None:
    result = compiler(FakeExpressionEngine()).compile(
        definition([
            NormalizedEdge("first", "END", "completed"),
            NormalizedEdge("first", "second"),
            NormalizedEdge("second", "END"),
        ])
    )
    source, router, path_map = result.conditional[0]
    assert source == "first"
    assert path_map == {"END": "__END__", "second": "second"}
    assert asyncio.run(router({"completed": True})) == "END"
    assert asyncio.run(router({"completed": False})) == "second"


def test_passes_checkpointer_and_store_to_langgraph_compile() -> None:
    checkpointer = Checkpointer()
    store = Store()
    result = compiler().compile(
        definition([
            NormalizedEdge("first", "second"),
            NormalizedEdge("second", "END"),
        ]),
        checkpointer=checkpointer,
        store=store,
    )
    assert result.compile_arguments == {
        "checkpointer": checkpointer,
        "store": store,
    }


def test_dynamic_state_schema_uses_declared_application_fields() -> None:
    schema = build_state_schema(
        NormalizedState(
            schema={
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "count": {"type": "integer"},
                },
            }
        )
    )
    assert schema.__annotations__ == {
        "question": str,
        "count": int,
    }
    assert schema.__total__ is False


def test_conditional_edges_require_one_default() -> None:
    with pytest.raises(GraphCompilerError, match="default"):
        compiler(FakeExpressionEngine()).compile(
            definition([
                NormalizedEdge("first", "END", "completed"),
                NormalizedEdge("second", "END"),
            ])
        )


def test_multiple_fixed_edges_are_rejected() -> None:
    with pytest.raises(GraphCompilerError, match="exactly one"):
        compiler().compile(
            definition([
                NormalizedEdge("first", "second"),
                NormalizedEdge("first", "END"),
                NormalizedEdge("second", "END"),
            ])
        )
