"""Load and validate declarative application-agent definitions."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


REQUIRED_DEFINITIONS: dict[str, str] = {
    "agent-definition.md": "agent",
    "workflow-definition.md": "workflow",
    "state-model.md": "state-model",
    "tools-and-capabilities.md": "tools-and-capabilities",
    "knowledge-model.md": "knowledge-model",
    "sequence-diagrams.md": "sequence-diagrams",
}

SUPPORTED_NODE_TYPES: set[str] = {
    "model",
    "operation",
    "capability",
    "approval",
}

SUPPORTED_FIELD_TYPES: set[str] = {
    "string",
    "boolean",
    "integer",
    "float",
    "object",
    "string_list",
    "object_list",
    "optional_string",
    "optional_int",
    "optional_float",
    "literal",
}


class AgentDefinitionError(ValueError):
    """Raised when an agent definition bundle is invalid."""


@dataclass(frozen=True)
class MarkdownDefinition:
    """One Markdown document and its parsed YAML front matter."""

    path: Path
    metadata: dict[str, Any]
    markdown: str

    @property
    def id(self) -> str:
        return str(self.metadata["id"])

    @property
    def version(self) -> str:
        return str(self.metadata["version"])

    @property
    def kind(self) -> str:
        return str(self.metadata["kind"])


@dataclass(frozen=True)
class AgentDefinitionBundle:
    """Validated collection of files defining one application agent."""

    agent_directory: Path
    definitions: dict[str, MarkdownDefinition]

    def get(self, filename: str) -> MarkdownDefinition:
        try:
            return self.definitions[filename]
        except KeyError as exc:
            raise AgentDefinitionError(
                f"Definition is not available: {filename}"
            ) from exc

    @property
    def agent(self) -> MarkdownDefinition:
        return self.get("agent-definition.md")

    @property
    def workflow(self) -> MarkdownDefinition:
        return self.get("workflow-definition.md")

    @property
    def state(self) -> MarkdownDefinition:
        return self.get("state-model.md")

    @property
    def capabilities(self) -> MarkdownDefinition:
        return self.get("tools-and-capabilities.md")

    @property
    def knowledge(self) -> MarkdownDefinition:
        return self.get("knowledge-model.md")

    @property
    def sequences(self) -> MarkdownDefinition:
        return self.get("sequence-diagrams.md")

    @property
    def agent_id(self) -> str:
        return self.agent.id

    @property
    def version(self) -> str:
        return self.agent.version

    @property
    def display_name(self) -> str:
        return str(
            self.agent.metadata.get(
                "display_name",
                self.agent_id,
            )
        )


class AgentRepository:
    """Discover and load agents from an agent repository."""

    def __init__(
        self,
        repository_directory: Path | str,
    ) -> None:
        self.repository_directory = Path(
            repository_directory
        ).resolve()

        if not self.repository_directory.is_dir():
            raise AgentDefinitionError(
                "Agent repository does not exist: "
                f"{self.repository_directory}"
            )

    def list_agent_directories(self) -> list[str]:
        """Return repository directories containing agent definitions."""

        result: list[str] = []

        for path in self.repository_directory.iterdir():
            if not path.is_dir():
                continue

            if (path / "agent-definition.md").is_file():
                result.append(path.name)

        return sorted(result)

    def contains(
        self,
        directory_name: str,
    ) -> bool:
        """Return whether an agent directory is discoverable."""

        if not isinstance(directory_name, str):
            return False

        normalized_name = directory_name.strip()

        if not normalized_name:
            return False

        return (
            self.repository_directory
            / normalized_name
            / "agent-definition.md"
        ).is_file()

    def load(
        self,
        directory_name: str,
    ) -> AgentDefinitionBundle:
        """Load one agent by its repository directory name."""

        if not isinstance(directory_name, str):
            raise AgentDefinitionError(
                "Agent directory name must be a string"
            )

        normalized_name = directory_name.strip()

        if not normalized_name:
            raise AgentDefinitionError(
                "Agent directory name must not be empty"
            )

        agent_directory = (
            self.repository_directory
            / normalized_name
        )

        return load_agent_definition(agent_directory)

    def load_all(
        self,
    ) -> dict[str, AgentDefinitionBundle]:
        """Load all discoverable agents, keyed by agent ID."""

        bundles: dict[str, AgentDefinitionBundle] = {}

        for directory_name in self.list_agent_directories():
            bundle = self.load(directory_name)

            if bundle.agent_id in bundles:
                existing = bundles[bundle.agent_id]

                raise AgentDefinitionError(
                    f"Duplicate agent ID {bundle.agent_id!r} in "
                    f"{existing.agent_directory} and "
                    f"{bundle.agent_directory}"
                )

            bundles[bundle.agent_id] = bundle

        return bundles


def split_front_matter(
    path: Path,
) -> tuple[dict[str, Any], str]:
    """Split YAML front matter from the Markdown body."""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AgentDefinitionError(
            f"Could not read definition file {path}: {exc}"
        ) from exc

    lines = text.splitlines()

    if not lines or lines[0].strip() != "---":
        raise AgentDefinitionError(
            f"{path} must start with a YAML front-matter marker"
        )

    try:
        closing_index = next(
            index
            for index, line in enumerate(
                lines[1:],
                start=1,
            )
            if line.strip() == "---"
        )
    except StopIteration as exc:
        raise AgentDefinitionError(
            f"{path} has no closing YAML front-matter marker"
        ) from exc

    yaml_text = "\n".join(lines[1:closing_index])
    markdown = "\n".join(
        lines[closing_index + 1 :]
    ).strip()

    try:
        metadata = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as exc:
        raise AgentDefinitionError(
            f"{path} contains invalid YAML front matter: {exc}"
        ) from exc

    if not isinstance(metadata, dict):
        raise AgentDefinitionError(
            f"{path} front matter must be a YAML mapping"
        )

    return metadata, markdown


def load_markdown_definition(
    path: Path,
    expected_kind: str,
) -> MarkdownDefinition:
    """Load and validate one Markdown definition document."""

    if not path.is_file():
        raise AgentDefinitionError(
            f"Required definition file is missing: {path}"
        )

    metadata, markdown = split_front_matter(path)

    for field_name in ("id", "version", "kind"):
        value = metadata.get(field_name)

        if value is None or str(value).strip() == "":
            raise AgentDefinitionError(
                f"{path} is missing required field "
                f"{field_name!r}"
            )

    actual_kind = str(metadata["kind"])

    if actual_kind != expected_kind:
        raise AgentDefinitionError(
            f"{path} has kind {actual_kind!r}; "
            f"expected {expected_kind!r}"
        )

    return MarkdownDefinition(
        path=path,
        metadata=metadata,
        markdown=markdown,
    )


def load_agent_definition(
    agent_directory: Path | str,
) -> AgentDefinitionBundle:
    """Load and validate one complete application-agent bundle."""

    agent_directory = Path(agent_directory).resolve()

    if not agent_directory.is_dir():
        raise AgentDefinitionError(
            f"Agent directory does not exist: {agent_directory}"
        )

    definitions: dict[str, MarkdownDefinition] = {}

    for filename, expected_kind in REQUIRED_DEFINITIONS.items():
        definitions[filename] = load_markdown_definition(
            agent_directory / filename,
            expected_kind,
        )

    bundle = AgentDefinitionBundle(
        agent_directory=agent_directory,
        definitions=definitions,
    )

    validate_agent_bundle(bundle)

    return bundle


def validate_agent_bundle(
    bundle: AgentDefinitionBundle,
) -> None:
    """Validate references across the complete bundle."""

    validate_agent_definition(bundle.agent)
    validate_state_model(bundle.state)
    validate_capability_definition(bundle.capabilities)
    validate_workflow_definition(bundle)
    validate_definition_identity(bundle)


def validate_agent_definition(
    definition: MarkdownDefinition,
) -> None:
    """Validate prompts and structured model declarations."""

    models = definition.metadata.get("models")
    prompts = definition.metadata.get("prompts")

    if not isinstance(models, dict) or not models:
        raise AgentDefinitionError(
            f"{definition.path} must declare at least one model"
        )

    if not isinstance(prompts, dict) or not prompts:
        raise AgentDefinitionError(
            f"{definition.path} must declare at least one prompt"
        )

    for prompt_name, prompt_text in prompts.items():
        if not isinstance(prompt_name, str):
            raise AgentDefinitionError(
                f"{definition.path} contains a non-string prompt name"
            )

        if not isinstance(prompt_text, str) or not prompt_text.strip():
            raise AgentDefinitionError(
                f"Prompt {prompt_name!r} must contain text"
            )

    for model_name, model_definition in models.items():
        if not isinstance(model_definition, dict):
            raise AgentDefinitionError(
                f"Model {model_name!r} must be a mapping"
            )

        fields = model_definition.get("fields")

        if not isinstance(fields, dict) or not fields:
            raise AgentDefinitionError(
                f"Model {model_name!r} must declare fields"
            )

        validate_fields(
            fields,
            location=f"model {model_name!r}",
        )


def validate_state_model(
    definition: MarkdownDefinition,
) -> None:
    """Validate the declared workflow state."""

    fields = definition.metadata.get("fields")

    if not isinstance(fields, dict) or not fields:
        raise AgentDefinitionError(
            f"{definition.path} must declare state fields"
        )

    validate_fields(
        fields,
        location="state model",
    )


def validate_fields(
    fields: dict[str, Any],
    location: str,
) -> None:
    """Validate field declarations used by state and models."""

    for field_name, field_definition in fields.items():
        if not isinstance(field_definition, dict):
            raise AgentDefinitionError(
                f"Field {field_name!r} in {location} "
                "must be a mapping"
            )

        field_type = field_definition.get("type")

        if field_type not in SUPPORTED_FIELD_TYPES:
            raise AgentDefinitionError(
                f"Field {field_name!r} in {location} uses "
                f"unsupported type {field_type!r}"
            )

        if field_type == "literal":
            values = field_definition.get("values")

            if not isinstance(values, list) or not values:
                raise AgentDefinitionError(
                    f"Literal field {field_name!r} in "
                    f"{location} must declare a non-empty "
                    "values list"
                )


def validate_capability_definition(
    definition: MarkdownDefinition,
) -> None:
    """Validate the logical capabilities declared by an agent."""

    capabilities = definition.metadata.get("capabilities")

    if not isinstance(capabilities, list) or not capabilities:
        raise AgentDefinitionError(
            f"{definition.path} must declare capabilities"
        )

    capability_ids: set[str] = set()

    for capability in capabilities:
        if not isinstance(capability, dict):
            raise AgentDefinitionError(
                "Each capability definition must be a mapping"
            )

        capability_id = required_string(
            capability,
            "id",
            "capability",
        )

        required_string(
            capability,
            "operation",
            f"capability {capability_id!r}",
        )

        if capability_id in capability_ids:
            raise AgentDefinitionError(
                f"Duplicate capability ID: {capability_id}"
            )

        capability_ids.add(capability_id)

        permissions = capability.get("permissions", [])

        if not isinstance(permissions, list):
            raise AgentDefinitionError(
                f"Capability {capability_id!r} permissions "
                "must be a list"
            )

        if not isinstance(
            capability.get("side_effect", False),
            bool,
        ):
            raise AgentDefinitionError(
                f"Capability {capability_id!r} side_effect "
                "must be true or false"
            )

        if not isinstance(
            capability.get("approval_required", False),
            bool,
        ):
            raise AgentDefinitionError(
                f"Capability {capability_id!r} "
                "approval_required must be true or false"
            )

        request_mapping = capability.get("request", {})

        if not isinstance(request_mapping, dict):
            raise AgentDefinitionError(
                f"Capability {capability_id!r} request "
                "must be a mapping"
            )

        result_mapping = capability.get("result", {})

        if not isinstance(result_mapping, dict):
            raise AgentDefinitionError(
                f"Capability {capability_id!r} result "
                "must be a mapping"
            )


def validate_workflow_definition(
    bundle: AgentDefinitionBundle,
) -> None:
    """Validate workflow nodes, edges, and references."""

    workflow = bundle.workflow.metadata
    agent = bundle.agent.metadata
    capability_metadata = bundle.capabilities.metadata

    nodes = workflow.get("nodes")
    edges = workflow.get("edges")
    entry_node = workflow.get("entry_node")

    if not isinstance(nodes, list) or not nodes:
        raise AgentDefinitionError(
            f"{bundle.workflow.path} must declare workflow nodes"
        )

    if not isinstance(edges, list) or not edges:
        raise AgentDefinitionError(
            f"{bundle.workflow.path} must declare workflow edges"
        )

    node_ids: set[str] = set()
    model_names = set(agent["models"])
    prompt_names = set(agent["prompts"])

    capability_ids = {
        capability["id"]
        for capability in capability_metadata["capabilities"]
    }

    for node in nodes:
        if not isinstance(node, dict):
            raise AgentDefinitionError(
                "Each workflow node must be a mapping"
            )

        node_id = required_string(
            node,
            "id",
            "workflow node",
        )

        node_type = required_string(
            node,
            "type",
            f"workflow node {node_id!r}",
        )

        if node_id in node_ids:
            raise AgentDefinitionError(
                f"Duplicate workflow node ID: {node_id}"
            )

        node_ids.add(node_id)

        if node_type not in SUPPORTED_NODE_TYPES:
            raise AgentDefinitionError(
                f"Workflow node {node_id!r} uses unsupported "
                f"type {node_type!r}"
            )

        validate_node_reference(
            node=node,
            node_id=node_id,
            node_type=node_type,
            prompt_names=prompt_names,
            model_names=model_names,
            capability_ids=capability_ids,
        )

    if not isinstance(entry_node, str):
        raise AgentDefinitionError(
            "Workflow entry_node must be a string"
        )

    if entry_node not in node_ids:
        raise AgentDefinitionError(
            f"Workflow entry node {entry_node!r} is not a "
            "declared node"
        )

    validate_workflow_edges(
        edges=edges,
        node_ids=node_ids,
    )

    validate_workflow_routing(
        workflow=workflow,
        node_ids=node_ids,
    )

    validate_approval_definitions(
        workflow=workflow,
        nodes=nodes,
    )


def validate_node_reference(
    node: dict[str, Any],
    node_id: str,
    node_type: str,
    prompt_names: set[str],
    model_names: set[str],
    capability_ids: set[str],
) -> None:
    """Validate references specific to each workflow node type."""

    if node_type == "model":
        prompt = required_string(
            node,
            "prompt",
            f"model node {node_id!r}",
        )

        output = required_string(
            node,
            "output",
            f"model node {node_id!r}",
        )

        if prompt not in prompt_names:
            raise AgentDefinitionError(
                f"Model node {node_id!r} references unknown "
                f"prompt {prompt!r}"
            )

        if output not in model_names:
            raise AgentDefinitionError(
                f"Model node {node_id!r} references unknown "
                f"model contract {output!r}"
            )

    elif node_type == "operation":
        required_string(
            node,
            "operation",
            f"operation node {node_id!r}",
        )

    elif node_type == "capability":
        capability_id = required_string(
            node,
            "capability",
            f"capability node {node_id!r}",
        )

        if capability_id not in capability_ids:
            raise AgentDefinitionError(
                f"Capability node {node_id!r} references "
                f"undeclared capability {capability_id!r}"
            )

    elif node_type == "approval":
        required_string(
            node,
            "approval",
            f"approval node {node_id!r}",
        )

        required_string(
            node,
            "decision_field",
            f"approval node {node_id!r}",
        )


def validate_workflow_edges(
    edges: list[Any],
    node_ids: set[str],
) -> None:
    """Validate that workflow edges reference existing nodes."""

    for edge in edges:
        if not isinstance(edge, dict):
            raise AgentDefinitionError(
                "Each workflow edge must be a mapping"
            )

        source = required_string(
            edge,
            "from",
            "workflow edge",
        )

        target = required_string(
            edge,
            "to",
            "workflow edge",
        )

        if source not in node_ids:
            raise AgentDefinitionError(
                f"Workflow edge has unknown source node "
                f"{source!r}"
            )

        if target != "END" and target not in node_ids:
            raise AgentDefinitionError(
                f"Workflow edge has unknown target node "
                f"{target!r}"
            )


def validate_workflow_routing(
    workflow: dict[str, Any],
    node_ids: set[str],
) -> None:
    """Validate routing defaults and conditional routes."""

    routing = workflow.get("routing", {})

    if routing is None:
        return

    if not isinstance(routing, dict):
        raise AgentDefinitionError(
            "Workflow routing must be a mapping"
        )

    defaults = routing.get("defaults", {})

    if not isinstance(defaults, dict):
        raise AgentDefinitionError(
            "Workflow routing defaults must be a mapping"
        )

    for source, target in defaults.items():
        validate_route_target(
            source=str(source),
            target=str(target),
            node_ids=node_ids,
            location="routing default",
        )

    conditions = routing.get("conditions", [])

    if not isinstance(conditions, list):
        raise AgentDefinitionError(
            "Workflow routing conditions must be a list"
        )

    for condition in conditions:
        if not isinstance(condition, dict):
            raise AgentDefinitionError(
                "Each routing condition must be a mapping"
            )

        source = required_string(
            condition,
            "from",
            "routing condition",
        )

        target = required_string(
            condition,
            "to",
            "routing condition",
        )

        required_string(
            condition,
            "when",
            "routing condition",
        )

        validate_route_target(
            source=source,
            target=target,
            node_ids=node_ids,
            location="routing condition",
        )


def validate_route_target(
    source: str,
    target: str,
    node_ids: set[str],
    location: str,
) -> None:
    """Validate one routing source and destination."""

    if source not in node_ids:
        raise AgentDefinitionError(
            f"{location} references unknown source node "
            f"{source!r}"
        )

    if target != "END" and target not in node_ids:
        raise AgentDefinitionError(
            f"{location} references unknown target node "
            f"{target!r}"
        )


def validate_approval_definitions(
    workflow: dict[str, Any],
    nodes: list[Any],
) -> None:
    """Validate declared approvals against approval workflow nodes."""

    approvals = workflow.get("approvals", [])

    if not isinstance(approvals, list):
        raise AgentDefinitionError(
            "Workflow approvals must be a list"
        )

    approval_ids: set[str] = set()

    for approval in approvals:
        if not isinstance(approval, dict):
            raise AgentDefinitionError(
                "Each approval definition must be a mapping"
            )

        approval_id = required_string(
            approval,
            "id",
            "approval definition",
        )

        if approval_id in approval_ids:
            raise AgentDefinitionError(
                f"Duplicate approval ID: {approval_id}"
            )

        approval_ids.add(approval_id)

    node_approval_ids = {
        node["approval"]
        for node in nodes
        if isinstance(node, dict)
        and node.get("type") == "approval"
    }

    undeclared = node_approval_ids - approval_ids

    if undeclared:
        raise AgentDefinitionError(
            "Workflow approval nodes reference undeclared "
            f"approvals: {sorted(undeclared)}"
        )


def validate_definition_identity(
    bundle: AgentDefinitionBundle,
) -> None:
    """Ensure every definition document has a unique ID."""

    definition_ids: set[str] = set()

    for definition in bundle.definitions.values():
        if definition.id in definition_ids:
            raise AgentDefinitionError(
                f"Duplicate definition ID {definition.id!r}"
            )

        definition_ids.add(definition.id)


def required_string(
    mapping: dict[str, Any],
    key: str,
    location: str,
) -> str:
    """Read a required, non-empty string field."""

    value = mapping.get(key)

    if not isinstance(value, str) or not value.strip():
        raise AgentDefinitionError(
            f"{location} must declare non-empty field {key!r}"
        )

    return value.strip()


def format_bundle_summary(
    bundle: AgentDefinitionBundle,
) -> str:
    """Create a concise validation summary."""

    workflow_nodes = bundle.workflow.metadata["nodes"]
    capabilities = bundle.capabilities.metadata["capabilities"]

    node_types = sorted(
        {
            node["type"]
            for node in workflow_nodes
        }
    )

    lines = [
        "Agent definition bundle is valid",
        f"Agent directory: {bundle.agent_directory}",
        f"Agent ID: {bundle.agent_id}",
        f"Display name: {bundle.display_name}",
        f"Version: {bundle.version}",
        f"Definitions: {len(bundle.definitions)}",
        f"Workflow nodes: {len(workflow_nodes)}",
        f"Node types: {', '.join(node_types)}",
        f"Capabilities: {len(capabilities)}",
    ]

    return "\n".join(lines)

def _validate_node_reference(
    *,
    reference: object,
    node_ids: set[str],
    context: str,
    allow_end: bool = False,
) -> None:
    """Validate that a workflow reference points to a declared node."""

    if not isinstance(reference, str) or not reference:
        raise AgentDefinitionError(
            f"{context} must reference a non-empty node ID"
        )

    allowed_references = set(node_ids)

    if allow_end:
        allowed_references.add("END")

    if reference not in allowed_references:
        available = ", ".join(sorted(allowed_references))

        raise AgentDefinitionError(
            f"{context} references unknown node {reference!r}. "
            f"Available references: {available}"
        )

def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Validate a declarative application-agent "
            "definition bundle"
        )
    )

    parser.add_argument(
        "agent_directory",
        nargs="?",
        default=(
            "./ai-enabled-analytics-v3/"
            "agents/opo-monitoring"
        ),
        help=(
            "Path to the application-agent directory. "
            "the Markdown definition files."
        ),
    )

    return parser


def main(
    arguments: Iterable[str] | None = None,
) -> int:
    """Validate an agent bundle from the command line."""

    parser = build_argument_parser()
    parsed = parser.parse_args(arguments)

    try:
        bundle = load_agent_definition(
            Path(parsed.agent_directory)
        )
    except AgentDefinitionError as exc:
        print(f"INVALID: {exc}")
        return 1

    print(format_bundle_summary(bundle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
