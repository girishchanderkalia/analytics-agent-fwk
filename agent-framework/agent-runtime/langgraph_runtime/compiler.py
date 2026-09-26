"""Compile normalized declarative agents into executable LangGraph graphs."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from definitions import NormalizedAgentDefinition, NormalizedEdge

from .compiler_errors import GraphCompilerError
from .routing import create_conditional_router
from .state_schema import build_state_schema
from .standard_nodes import StandardNodeLibrary


class LangGraphCompiler:
    """Make LangGraph the central execution engine for normalized agents."""

    def __init__(
        self,
        node_library: StandardNodeLibrary,
        *,
        expression_engine: Any = None,
        state_graph_factory: Any = None,
        end_marker: Any = None,
    ) -> None:
        self.node_library = node_library
        self.expression_engine = expression_engine
        self._state_graph_factory = state_graph_factory
        self._end_marker = end_marker

    def compile(
        self,
        definition: NormalizedAgentDefinition,
        *,
        checkpointer: Any = None,
        store: Any = None,
    ) -> Any:
        """Compile one normalized definition to a LangGraph executable."""

        graph_factory, end_marker = self._langgraph_components()
        state_schema = build_state_schema(
            definition.state,
            name=_schema_name(definition.agent_id),
        )
        builder = graph_factory(state_schema)

        for node in definition.graph.nodes:
            builder.add_node(
                node.node_id,
                self.node_library.create(node),
            )

        builder.set_entry_point(definition.graph.entry_node)
        edges_by_source = _group_edges(definition.graph.edges)

        for source, edges in edges_by_source.items():
            conditioned = [edge for edge in edges if edge.condition is not None]
            if conditioned:
                router = create_conditional_router(
                    edges,
                    self.expression_engine,
                )
                targets = {
                    edge.target: (
                        end_marker if edge.target == "END" else edge.target
                    )
                    for edge in edges
                }
                builder.add_conditional_edges(
                    source,
                    router,
                    targets,
                )
                continue

            if len(edges) != 1:
                raise GraphCompilerError(
                    f"Node {source!r} must have exactly one fixed edge"
                )
            target = edges[0].target
            builder.add_edge(
                source,
                end_marker if target == "END" else target,
            )

        compile_arguments = {}
        if checkpointer is not None:
            compile_arguments["checkpointer"] = checkpointer
        if store is not None:
            compile_arguments["store"] = store
        return builder.compile(**compile_arguments)

    def _langgraph_components(self) -> tuple[Any, Any]:
        if self._state_graph_factory is not None:
            if self._end_marker is None:
                raise GraphCompilerError(
                    "An injected StateGraph factory requires an END marker"
                )
            return self._state_graph_factory, self._end_marker

        try:
            from langgraph.graph import END, StateGraph
        except ImportError as exc:
            raise GraphCompilerError(
                "LangGraph is not installed"
            ) from exc
        return StateGraph, END


def _group_edges(
    edges: tuple[NormalizedEdge, ...],
) -> dict[str, tuple[NormalizedEdge, ...]]:
    grouped: defaultdict[str, list[NormalizedEdge]] = defaultdict(list)
    for edge in edges:
        grouped[edge.source].append(edge)
    return {
        source: tuple(source_edges)
        for source, source_edges in grouped.items()
    }


def _schema_name(agent_id: str) -> str:
    normalized = "".join(
        character if character.isalnum() else "_"
        for character in agent_id
    ).strip("_")
    return f"{normalized or 'Agent'}State"
