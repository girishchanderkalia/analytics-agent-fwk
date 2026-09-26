"""Normalize registered package sources without interpreting domain content."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from mcp_tools import AgentToolReference

from .normalization_errors import DefinitionNormalizationError
from .normalized_models import (
    NormalizedAgentDefinition,
    NormalizedEdge,
    NormalizedGraph,
    NormalizedNode,
    NormalizedPrompt,
    NormalizedState,
)
from .source_loader import LoadedAgentPackage, load_agent_package


END = "END"


def normalize_agent_package(
    package_root: Path | str,
) -> NormalizedAgentDefinition:
    """Load and normalize one explicitly registered declarative package."""

    package = load_agent_package(package_root)
    return normalize_loaded_package(package)


def normalize_loaded_package(
    package: LoadedAgentPackage,
) -> NormalizedAgentDefinition:
    """Normalize sources assigned to generic package roles."""

    graph = _normalize_graph(_read_yaml(package.source("graph"), "graph"))
    state = _normalize_state(_read_yaml(package.source("state"), "state"))
    prompts = _normalize_prompts(_optional_yaml(package, "prompts"))
    tools = _normalize_tools(_optional_yaml(package, "tools"))
    knowledge = tuple(
        path.read_text(encoding="utf-8")
        for role, path in package.resolved_sources
        if role.startswith("knowledge[")
    )

    return NormalizedAgentDefinition(
        agent_id=package.manifest.agent_id,
        version=package.manifest.version,
        graph=graph,
        state=state,
        prompts=prompts,
        tools=tools,
        knowledge=knowledge,
        metadata=dict(package.manifest.metadata),
    )


def _normalize_graph(raw: object) -> NormalizedGraph:
    data = _mapping(raw, "graph")
    entry = _text(data.get("entry"), "graph.entry")
    raw_nodes = _list(data.get("nodes"), "graph.nodes")
    raw_edges = _list(data.get("edges"), "graph.edges")

    nodes: list[NormalizedNode] = []
    node_ids: set[str] = set()
    for index, item in enumerate(raw_nodes):
        node = _mapping(item, f"graph.nodes[{index}]")
        node_id = _text(node.get("id"), f"graph.nodes[{index}].id")
        kind = _text(node.get("kind"), f"graph.nodes[{index}].kind")
        if node_id == END:
            raise DefinitionNormalizationError("END is reserved and cannot be a node ID")
        if node_id in node_ids:
            raise DefinitionNormalizationError(f"Duplicate graph node ID: {node_id}")
        config = node.get("config", {})
        if not isinstance(config, Mapping):
            raise DefinitionNormalizationError(
                f"graph.nodes[{index}].config must be a mapping"
            )
        nodes.append(NormalizedNode(node_id=node_id, kind=kind, config=dict(config)))
        node_ids.add(node_id)

    if entry not in node_ids:
        raise DefinitionNormalizationError(
            f"Graph entry node is not declared: {entry}"
        )

    edges: list[NormalizedEdge] = []
    for index, item in enumerate(raw_edges):
        edge = _mapping(item, f"graph.edges[{index}]")
        source = _text(edge.get("from"), f"graph.edges[{index}].from")
        target = _text(edge.get("to"), f"graph.edges[{index}].to")
        condition = edge.get("condition")
        if condition is not None:
            condition = _text(condition, f"graph.edges[{index}].condition")
        if source not in node_ids:
            raise DefinitionNormalizationError(
                f"Graph edge source is not declared: {source}"
            )
        if target != END and target not in node_ids:
            raise DefinitionNormalizationError(
                f"Graph edge target is not declared: {target}"
            )
        edges.append(NormalizedEdge(source=source, target=target, condition=condition))

    return NormalizedGraph(entry_node=entry, nodes=tuple(nodes), edges=tuple(edges))


def _normalize_state(raw: object) -> NormalizedState:
    schema = _mapping(raw, "state")
    if schema.get("type", "object") != "object":
        raise DefinitionNormalizationError("State schema type must be 'object'")
    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping):
        raise DefinitionNormalizationError("state.properties must be a mapping")
    normalized = dict(schema)
    normalized.setdefault("type", "object")
    normalized["properties"] = dict(properties)
    return NormalizedState(schema=normalized)


def _normalize_prompts(raw: object | None) -> tuple[NormalizedPrompt, ...]:
    if raw is None:
        return ()
    data = _mapping(raw, "prompts")
    items = data.get("prompts", data)
    items = _mapping(items, "prompts.prompts")
    result: list[NormalizedPrompt] = []
    for prompt_id, value in items.items():
        prompt_id = _text(prompt_id, "prompt ID")
        if isinstance(value, str):
            result.append(NormalizedPrompt(prompt_id, value))
            continue
        definition = _mapping(value, f"prompt {prompt_id}")
        template = _text(definition.get("template"), f"prompt {prompt_id}.template")
        metadata = definition.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise DefinitionNormalizationError(
                f"prompt {prompt_id}.metadata must be a mapping"
            )
        result.append(NormalizedPrompt(prompt_id, template, dict(metadata)))
    return tuple(result)


def _normalize_tools(raw: object | None) -> tuple[AgentToolReference, ...]:
    if raw is None:
        return ()
    data = _mapping(raw, "tools")
    items = _list(data.get("tools", []), "tools.tools")
    result: list[AgentToolReference] = []
    identities: set[tuple[str, str, str | None]] = set()
    for index, item in enumerate(items):
        definition = _mapping(item, f"tools.tools[{index}]")
        reference = AgentToolReference(
            name=_text(definition.get("name"), f"tools.tools[{index}].name"),
            version=_text(definition.get("version"), f"tools.tools[{index}].version"),
            server=(
                None
                if definition.get("server") is None
                else _text(definition.get("server"), f"tools.tools[{index}].server")
            ),
        )
        identity = (reference.name, reference.version, reference.server)
        if identity in identities:
            raise DefinitionNormalizationError(
                f"Duplicate agent tool reference: {reference.name}@{reference.version}"
            )
        identities.add(identity)
        result.append(reference)
    return tuple(result)


def _optional_yaml(package: LoadedAgentPackage, role: str) -> object | None:
    source_map = dict(package.resolved_sources)
    path = source_map.get(role)
    return None if path is None else _read_yaml(path, role)


def _read_yaml(path: Path, role: str) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DefinitionNormalizationError(
            f"Could not read {role} source {path}: {exc}"
        ) from exc
    except yaml.YAMLError as exc:
        raise DefinitionNormalizationError(
            f"Invalid YAML in {role} source {path}: {exc}"
        ) from exc


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DefinitionNormalizationError(f"{field_name} must be a mapping")
    return value


def _list(value: object, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise DefinitionNormalizationError(f"{field_name} must be a list")
    return value


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DefinitionNormalizationError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()
