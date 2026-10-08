"""Expand the author-facing single-file format into the existing bundle contract."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from execution.definition_loader import (
    AgentDefinitionBundle,
    AgentDefinitionError,
    MarkdownDefinition,
    REQUIRED_DEFINITIONS,
    required_string,
)


def expand_agent_definition(document: MarkdownDefinition) -> AgentDefinitionBundle:
    authored = deepcopy(document.metadata)
    steps = authored.pop("steps", None)
    if not isinstance(steps, list) or not steps:
        raise AgentDefinitionError("agent.md must declare a non-empty steps list")
    knowledge = authored.pop("knowledge", None)
    if not isinstance(knowledge, dict):
        raise AgentDefinitionError("agent.md must declare knowledge with always and topics")
    always = knowledge.get("always", "")
    topics = knowledge.get("topics", {})
    if not isinstance(always, str) or not isinstance(topics, dict):
        raise AgentDefinitionError("knowledge.always must be text and topics a mapping")
    for name, content in topics.items():
        if not isinstance(content, str) or not content.strip():
            raise AgentDefinitionError(f"Knowledge topic {name!r} must contain text")
    fields = authored.pop("state", {})
    if not isinstance(fields, dict):
        raise AgentDefinitionError("state must be a mapping")
    fields = {
        "question": {"type": "string", "default": ""},
        "conversation_context": {"type": "object", "default": {}},
        **fields,
    }
    prompts: dict[str, str] = {}
    models: dict[str, Any] = {}
    capabilities: list[dict[str, Any]] = []
    approvals: list[dict[str, Any]] = []
    labels: dict[str, Any] = {}
    nodes: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            raise AgentDefinitionError("Each step must be a mapping")
        node = deepcopy(step)
        node_id = required_string(node, "id", "step")
        node_type = required_string(node, "type", f"step {node_id!r}")
        selected = node.pop("knowledge", [])
        if not isinstance(selected, list) or any(
            not isinstance(name, str) or name not in topics for name in selected
        ):
            raise AgentDefinitionError(f"Step {node_id!r} references unknown knowledge topics")
        if selected and node_type != "model":
            raise AgentDefinitionError(f"Only model steps may select knowledge: {node_id!r}")
        description = node.pop("description", "")
        output_to = node.get("output_to")
        if output_to:
            fields.setdefault(output_to, {"type": "object", "default": None})
            if description:
                labels[output_to] = {"description": description}
        if node_type == "model":
            instructions = required_string(node, "instructions", f"step {node_id!r}")
            node.pop("instructions")
            output = node.get("output")
            if not isinstance(output, dict) or not output:
                raise AgentDefinitionError(f"Model step {node_id!r} must declare output fields")
            sections = [instructions]
            for name in selected:
                sections.append(f"Domain knowledge ({name}):\n{topics[name].strip()}")
            prompts[node_id] = "\n\n".join(sections)
            models[node_id] = {"fields": output}
            node["prompt"] = node_id
            node["output"] = node_id
            required_string(node, "output_to", f"step {node_id!r}")
        elif node_type == "capability":
            binding = node.get("capability")
            if not isinstance(binding, dict):
                raise AgentDefinitionError(f"Step {node_id!r} capability must be a mapping")
            capabilities.append({**binding, "id": node_id})
            node["capability"] = node_id
        elif node_type == "approval":
            approval = node.pop("approval", {})
            if not isinstance(approval, dict):
                raise AgentDefinitionError(f"Step {node_id!r} approval must be a mapping")
            approval_id = approval.get("id", node_id)
            approvals.append({**approval, "id": approval_id})
            node["approval"] = approval_id
            responses = node.pop("responses", {})
            if not isinstance(responses, dict) or not responses:
                raise AgentDefinitionError(f"Approval step {node_id!r} must declare responses")
            decision_fields = {}
            for name, response in responses.items():
                if not isinstance(response, dict):
                    raise AgentDefinitionError(f"Approval response {name!r} must be a mapping")
                source = response.pop("from", name)
                fields.setdefault(name, response)
                decision_fields[name] = source
            node["decision_fields"] = decision_fields
            node.setdefault("decision_field", next(iter(responses)))
        nodes.append(node)
    for name, field in fields.items():
        if isinstance(field, dict) and field.get("description"):
            labels.setdefault(name, {"description": field["description"]})
    edges = [
        {"from": node["id"], "to": nodes[index + 1]["id"] if index + 1 < len(nodes) else "END"}
        for index, node in enumerate(nodes)
    ]
    routing = authored.pop("routing", {})
    workflow = {
        "entry_node": authored.pop("entry_node", nodes[0]["id"]),
        "nodes": nodes,
        "edges": authored.pop("edges", edges),
        "routing": routing,
        "approvals": approvals,
    }
    agent = {**authored, "models": models, "prompts": prompts}
    sections = {
        "agent-definition.md": (agent, document.markdown),
        "workflow-definition.md": (workflow, ""),
        "state-model.md": ({"fields": fields}, ""),
        "tools-and-capabilities.md": ({"capabilities": capabilities}, ""),
        "knowledge-model.md": ({"evidence_labels": labels}, always.strip()),
        "sequence-diagrams.md": ({}, ""),
    }
    definitions = {}
    for filename, (metadata, markdown) in sections.items():
        kind = REQUIRED_DEFINITIONS[filename]
        definitions[filename] = MarkdownDefinition(
            path=document.path,
            metadata={
                **metadata,
                "id": document.id if kind == "agent" else f"{document.id}-{kind}",
                "version": document.version,
                "kind": kind,
            },
            markdown=markdown,
        )
    return AgentDefinitionBundle(document.path.parent, definitions)