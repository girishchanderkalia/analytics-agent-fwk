"""Translate authored markdown agent packages into the normalized form.

Agent developers author markdown; the framework owns the internal shape the
graph compiler consumes, so agent packages never encode LangGraph concepts.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

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

END = "END"

# Authored node types map onto framework node kinds. Anything reaching outside
# the runtime is a tool call, regardless of who owns the service behind it.
NODE_KINDS = {
    "model": "model",
    "capability": "tool",
    "operation": "tool",
    "approval": "interrupt",
}

FIELD_TYPES: dict[str, dict[str, Any]] = {
    "string": {"type": "string"},
    "boolean": {"type": "boolean"},
    "integer": {"type": "integer"},
    "float": {"type": "number"},
    "object": {"type": "object"},
    "string_list": {"type": "array", "items": {"type": "string"}},
    "object_list": {"type": "array", "items": {"type": "object"}},
    "optional_string": {"type": ["string", "null"]},
    "optional_int": {"type": ["integer", "null"]},
    "optional_float": {"type": ["number", "null"]},
}


def translate_markdown_agent(
    agent_directory: Path | str,
) -> NormalizedAgentDefinition:
    """Load and translate one authored markdown agent package."""

    from execution.definition_loader import load_agent_definition

    return translate_bundle(load_agent_definition(agent_directory))


def translate_bundle(bundle: Any) -> NormalizedAgentDefinition:
    """Translate an already loaded markdown bundle."""

    agent = bundle.agent.metadata
    workflow = bundle.workflow.metadata
    capabilities = bundle.capabilities.metadata

    bindings = _tool_bindings(capabilities)
    nodes, extra_edges = _nodes(workflow, bindings)
    node_ids = {node.node_id for node in nodes}

    return NormalizedAgentDefinition(
        agent_id=bundle.agent_id,
        version=bundle.version,
        graph=NormalizedGraph(
            entry_node=_entry_node(workflow, node_ids),
            nodes=nodes,
            edges=_edges(workflow, node_ids, extra_edges),
        ),
        state=NormalizedState(
            schema=_state_schema(bundle.state.metadata, _tool_result_keys(nodes))
        ),
        prompts=_prompts(agent),
        tools=_tools(bindings),
        knowledge=(bundle.knowledge.markdown,),
        metadata={
            "display_name": bundle.display_name,
            "models": dict(agent.get("models", {})),
        },
    )


def _tool_bindings(
    capabilities: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Index capability and operation declarations by the ID nodes reference."""

    bindings: dict[str, dict[str, Any]] = {}

    for section in ("capabilities", "operations"):
        declared = capabilities.get(section, [])
        if not isinstance(declared, list):
            raise DefinitionNormalizationError(
                f"{section} must be a list"
            )
        for declaration in declared:
            if not isinstance(declaration, Mapping):
                raise DefinitionNormalizationError(
                    f"Each {section} declaration must be a mapping"
                )
            identifier = _text(declaration.get("id"), f"{section} id")
            if identifier in bindings:
                raise DefinitionNormalizationError(
                    f"Duplicate declaration: {identifier}"
                )
            bindings[identifier] = dict(declaration)

    return bindings


def _nodes(
    workflow: Mapping[str, Any],
    bindings: Mapping[str, Mapping[str, Any]],
) -> tuple[tuple[NormalizedNode, ...], list[NormalizedEdge]]:
    declared = workflow.get("nodes")
    if not isinstance(declared, list) or not declared:
        raise DefinitionNormalizationError("Workflow must declare nodes")

    nodes: list[NormalizedNode] = []
    extra_edges: list[NormalizedEdge] = []

    for node in declared:
        if not isinstance(node, Mapping):
            raise DefinitionNormalizationError(
                "Each workflow node must be a mapping"
            )
        node_id = _text(node.get("id"), "node id")
        node_type = _text(node.get("type"), f"node {node_id} type")

        try:
            kind = NODE_KINDS[node_type]
        except KeyError as exc:
            raise DefinitionNormalizationError(
                f"Node {node_id!r} has unsupported type {node_type!r}"
            ) from exc

        if kind == "model":
            nodes.append(
                NormalizedNode(node_id, kind, _model_config(node, node_id))
            )
            continue

        if kind == "interrupt":
            nodes.append(
                NormalizedNode(node_id, kind, _interrupt_config(node, node_id))
            )
            continue

        tool_node, mapping_node = _tool_nodes(node, node_id, bindings)
        nodes.append(tool_node)
        if mapping_node is not None:
            nodes.append(mapping_node)
            extra_edges.append(
                NormalizedEdge(source=tool_node.node_id, target=mapping_node.node_id)
            )

    return tuple(nodes), extra_edges


def _model_config(node: Mapping[str, Any], node_id: str) -> dict[str, Any]:
    contract = node.get("output_contract") or node.get("output")
    config = {
        "prompt": _text(node.get("prompt"), f"node {node_id} prompt"),
        "output_contract": _text(contract, f"node {node_id} output"),
        "result_key": _text(
            node.get("output_to") or node.get("writes"),
            f"node {node_id} output_to",
        ),
    }
    inputs = node.get("inputs")
    if inputs is not None:
        if not isinstance(inputs, list):
            raise DefinitionNormalizationError(
                f"Node {node_id!r} inputs must be a list"
            )
        config["inputs"] = [str(item) for item in inputs]
    return config


def _interrupt_config(node: Mapping[str, Any], node_id: str) -> dict[str, Any]:
    payload = node.get("payload", {})
    if not isinstance(payload, Mapping):
        raise DefinitionNormalizationError(
            f"Node {node_id!r} payload must be a mapping"
        )
    decision_fields = node.get("decision_fields", {})
    if not isinstance(decision_fields, Mapping):
        raise DefinitionNormalizationError(
            f"Node {node_id!r} decision_fields must be a mapping"
        )
    return {
        "payload": _references(payload),
        "result_key": _text(
            node.get("decision_field"),
            f"node {node_id} decision_field",
        ),
        "decision_fields": dict(decision_fields),
        "selection_from": node.get("selection_from"),
    }


def _tool_nodes(
    node: Mapping[str, Any],
    node_id: str,
    bindings: Mapping[str, Mapping[str, Any]],
) -> tuple[NormalizedNode, NormalizedNode | None]:
    """Build the tool node and, when results scatter, a mapping node."""

    reference = node.get("capability") or node.get("operation")
    identifier = _text(reference, f"node {node_id} capability or operation")

    try:
        binding = bindings[identifier]
    except KeyError as exc:
        raise DefinitionNormalizationError(
            f"Node {node_id!r} references undeclared {identifier!r}"
        ) from exc

    raw_key = f"{node_id}__result"
    tool_node = NormalizedNode(
        node_id,
        "tool",
        {
            "tool": _text(binding.get("tool"), f"{identifier} tool"),
            "version": str(binding.get("version", "1")),
            "server": _text(binding.get("server"), f"{identifier} server"),
            "arguments": _references(binding.get("request", {})),
            "result_key": raw_key,
        },
    )

    assignments = {
        target: _reference(expression, f"{identifier} result", raw_key)
        for target, expression in (binding.get("result") or {}).items()
    }
    if not assignments:
        return tool_node, None

    mapping_node = NormalizedNode(
        f"{node_id}__map",
        "transform",
        {"assignments": assignments},
    )
    return tool_node, mapping_node


def _edges(
    workflow: Mapping[str, Any],
    node_ids: set[str],
    extra_edges: list[NormalizedEdge],
) -> tuple[NormalizedEdge, ...]:
    declared = workflow.get("edges")
    if not isinstance(declared, list) or not declared:
        raise DefinitionNormalizationError("Workflow must declare edges")

    routing = workflow.get("routing") or {}
    conditions = routing.get("conditions") or []
    mapped = {edge.source: edge.target for edge in extra_edges}

    edges: list[NormalizedEdge] = list(extra_edges)

    for edge in declared:
        if not isinstance(edge, Mapping):
            raise DefinitionNormalizationError("Each edge must be a mapping")
        source = _text(edge.get("from"), "edge from")
        target = _text(edge.get("to"), "edge to")
        edges.append(
            NormalizedEdge(
                source=mapped.get(source, source),
                target=_resolve_target(target, node_ids),
            )
        )

    for condition in conditions:
        if not isinstance(condition, Mapping):
            raise DefinitionNormalizationError(
                "Each routing condition must be a mapping"
            )
        source = _text(condition.get("from"), "condition from")
        edges.append(
            NormalizedEdge(
                source=mapped.get(source, source),
                target=_resolve_target(
                    _text(condition.get("to"), "condition to"),
                    node_ids,
                ),
                condition=_text(condition.get("when"), "condition when"),
            )
        )

    return tuple(edges)


def _resolve_target(target: str, node_ids: set[str]) -> str:
    if target == END:
        return END
    if target in node_ids:
        return target
    raise DefinitionNormalizationError(
        f"Edge target is not a declared node: {target}"
    )


def _entry_node(workflow: Mapping[str, Any], node_ids: set[str]) -> str:
    entry = _text(workflow.get("entry_node"), "entry_node")
    if entry not in node_ids:
        raise DefinitionNormalizationError(
            f"Entry node is not declared: {entry}"
        )
    return entry


def _tool_result_keys(nodes: tuple[NormalizedNode, ...]) -> set[str]:
    """Raw tool results are graph state, so they must be declared as such."""

    return {
        str(node.config["result_key"])
        for node in nodes
        if node.kind == "tool" and "result_key" in node.config
    }


def _state_schema(
    state: Mapping[str, Any],
    tool_result_keys: set[str] | None = None,
) -> dict[str, Any]:
    fields = state.get("fields")
    if not isinstance(fields, Mapping):
        raise DefinitionNormalizationError("State model must declare fields")

    properties: dict[str, Any] = {}
    for name, definition in fields.items():
        if not isinstance(definition, Mapping):
            raise DefinitionNormalizationError(
                f"State field {name!r} must be a mapping"
            )
        declared = definition.get("type")
        if declared == "literal":
            schema: dict[str, Any] = {"enum": list(definition.get("values", []))}
        else:
            try:
                schema = dict(FIELD_TYPES[str(declared)])
            except KeyError as exc:
                raise DefinitionNormalizationError(
                    f"State field {name!r} has unsupported type {declared!r}"
                ) from exc
        if "default" in definition:
            schema["default"] = definition["default"]
        if definition.get("description"):
            schema["description"] = str(definition["description"]).strip()
        properties[str(name)] = schema

    for key in sorted(tool_result_keys or ()):
        properties.setdefault(key, {"type": "object", "default": None})

    return {"type": "object", "properties": properties}


def _prompts(agent: Mapping[str, Any]) -> tuple[NormalizedPrompt, ...]:
    prompts = agent.get("prompts") or {}
    if not isinstance(prompts, Mapping):
        raise DefinitionNormalizationError("prompts must be a mapping")
    return tuple(
        NormalizedPrompt(prompt_id=str(name), template=str(template))
        for name, template in prompts.items()
    )


def _tools(
    bindings: Mapping[str, Mapping[str, Any]],
) -> tuple[AgentToolReference, ...]:
    references = {
        (
            _text(binding.get("tool"), f"{identifier} tool"),
            str(binding.get("version", "1")),
            _text(binding.get("server"), f"{identifier} server"),
        )
        for identifier, binding in bindings.items()
    }
    return tuple(
        AgentToolReference(name=name, version=version, server=server)
        for name, version, server in sorted(references)
    )


def _references(value: Any) -> Any:
    """Rewrite authored `${state.x}` references to runtime `$.x` references."""

    if isinstance(value, str):
        return _reference(value, "request", None)
    if isinstance(value, Mapping):
        return {key: _references(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_references(item) for item in value]
    return value


def _reference(value: Any, context: str, result_key: str | None) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text.startswith("${state.") and text.endswith("}"):
        return "$." + text[len("${state.") : -1]
    if text.startswith("${result") and text.endswith("}"):
        if result_key is None:
            raise DefinitionNormalizationError(
                f"{context} cannot reference a result here: {value}"
            )
        suffix = text[len("${result") : -1].lstrip(".")
        return f"$.{result_key}" + (f".{suffix}" if suffix else "")
    return value


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DefinitionNormalizationError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()
