"""Validation pipeline for imported declarative agent bundles."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import yaml

from .models import (
    AgentBundleDocument,
    AgentDocumentType,
    DOCUMENT_SPECS,
    ValidationIssue,
    ValidationResult,
)


class AgentBundleValidator:
    """Validate bundle structure, front matter, and cross references."""

    def __init__(
        self,
        available_capabilities: frozenset[str] = frozenset(),
        available_operations: frozenset[str] = frozenset(),
    ) -> None:
        self.available_capabilities = available_capabilities
        self.available_operations = available_operations

    def validate(
        self,
        manifest: Mapping[str, Any],
        documents: tuple[AgentBundleDocument, ...],
    ) -> ValidationResult:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        by_type = {document.document_type: document for document in documents}
        metadata: dict[AgentDocumentType, dict[str, Any]] = {}

        agent_id = manifest.get("agentId")
        if not isinstance(agent_id, str) or not agent_id.strip():
            errors.append(ValidationIssue("MANIFEST_AGENT_ID", "manifest.agentId is required"))
        if manifest.get("schemaVersion") != "1.0":
            errors.append(ValidationIssue("SCHEMA_VERSION", "schemaVersion must be '1.0'"))

        for document_type, spec in DOCUMENT_SPECS.items():
            document = by_type.get(document_type)
            if spec.get("required") and document is None:
                errors.append(
                    ValidationIssue(
                        "REQUIRED_DOCUMENT_MISSING",
                        f"Required document is missing: {spec['file_name']}",
                        document_type=document_type.value,
                        file_name=spec["file_name"],
                    )
                )
                continue
            if document is None:
                continue
            parsed, issue = _parse_front_matter(document)
            if issue is not None:
                errors.append(issue)
            elif parsed is not None:
                metadata[document_type] = parsed
                expected_kind = document_type.value
                actual_kind = parsed.get("kind")
                kind_aliases = {
                    AgentDocumentType.STATE: {"state", "state-model"},
                    AgentDocumentType.CAPABILITIES: {"capabilities", "tools-and-capabilities"},
                    AgentDocumentType.DOCUMENTATION: {"documentation", "sequence-diagrams"},
                }
                allowed = kind_aliases.get(document_type, {expected_kind})
                if actual_kind not in allowed:
                    errors.append(
                        ValidationIssue(
                            "DOCUMENT_KIND",
                            f"Expected kind in {sorted(allowed)}, found {actual_kind!r}",
                            document_type=document_type.value,
                            file_name=document.file_name,
                            path="kind",
                        )
                    )

        agent_meta = metadata.get(AgentDocumentType.AGENT, {})
        declared_id = agent_meta.get("id")
        if agent_id and declared_id and declared_id != agent_id:
            errors.append(
                ValidationIssue(
                    "AGENT_ID_MISMATCH",
                    "manifest.agentId and agent-definition.md id must match",
                    document_type="agent",
                    file_name="agent-definition.md",
                    path="id",
                )
            )

        workflow = metadata.get(AgentDocumentType.WORKFLOW, {})
        nodes = workflow.get("nodes", [])
        if isinstance(nodes, list):
            capability_refs = {
                node.get("capability")
                for node in nodes
                if isinstance(node, Mapping) and node.get("type") == "capability"
            }
            operation_refs = {
                node.get("implementation") or node.get("operation")
                for node in nodes
                if isinstance(node, Mapping)
                and node.get("type") in {"operation", "deterministic"}
            }
            capability_refs.discard(None)
            operation_refs.discard(None)

            if capability_refs and AgentDocumentType.CAPABILITIES not in by_type:
                errors.append(
                    ValidationIssue(
                        "CAPABILITIES_DOCUMENT_REQUIRED",
                        "tools-and-capabilities.md is required when capability nodes are present",
                        document_type="capabilities",
                        file_name="tools-and-capabilities.md",
                    )
                )

            if self.available_capabilities:
                for reference in sorted(capability_refs - self.available_capabilities):
                    errors.append(
                        ValidationIssue(
                            "CAPABILITY_NOT_REGISTERED",
                            f"Capability is not registered: {reference}",
                            document_type="workflow",
                            file_name="workflow-definition.md",
                        )
                    )
            if self.available_operations:
                for reference in sorted(operation_refs - self.available_operations):
                    errors.append(
                        ValidationIssue(
                            "OPERATION_NOT_REGISTERED",
                            f"Operation is not registered: {reference}",
                            document_type="workflow",
                            file_name="workflow-definition.md",
                        )
                    )

        if AgentDocumentType.KNOWLEDGE not in by_type:
            warnings.append(
                ValidationIssue(
                    "KNOWLEDGE_MODEL_MISSING",
                    "No knowledge-model.md was supplied",
                    severity="warning",
                    document_type="knowledge",
                    file_name="knowledge-model.md",
                )
            )

        return ValidationResult(tuple(errors), tuple(warnings))


def _parse_front_matter(
    document: AgentBundleDocument,
) -> tuple[dict[str, Any] | None, ValidationIssue | None]:
    text = document.content
    if any(fragment in text.lower() for fragment in ("<br", "&lt;", "&gt;", "content goes here")):
        return None, ValidationIssue(
            "COPY_ARTIFACT",
            "Document contains an HTML or placeholder artifact",
            document_type=document.document_type.value,
            file_name=document.file_name,
        )
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, ValidationIssue(
            "FRONT_MATTER_MISSING",
            "Document must start with YAML front matter",
            document_type=document.document_type.value,
            file_name=document.file_name,
            line=1,
        )
    try:
        closing = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return None, ValidationIssue(
            "FRONT_MATTER_UNCLOSED",
            "YAML front matter is not closed",
            document_type=document.document_type.value,
            file_name=document.file_name,
        )
    try:
        parsed = yaml.safe_load("\n".join(lines[1:closing])) or {}
    except yaml.YAMLError as exc:
        return None, ValidationIssue(
            "FRONT_MATTER_YAML",
            f"Invalid YAML front matter: {exc}",
            document_type=document.document_type.value,
            file_name=document.file_name,
        )
    if not isinstance(parsed, dict):
        return None, ValidationIssue(
            "FRONT_MATTER_TYPE",
            "YAML front matter must be a mapping",
            document_type=document.document_type.value,
            file_name=document.file_name,
        )
    if not "\n".join(lines[closing + 1:]).strip():
        return None, ValidationIssue(
            "MARKDOWN_BODY_EMPTY",
            "Markdown body must not be empty",
            document_type=document.document_type.value,
            file_name=document.file_name,
        )
    return parsed, None
