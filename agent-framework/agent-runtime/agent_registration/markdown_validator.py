"""Registration validator for authored markdown agent packages."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from definitions import DefinitionNormalizationError, translate_bundle
from execution.definition_loader import (
    REQUIRED_DEFINITIONS,
    AgentDefinitionError,
    load_agent_definition,
)

from .errors import AgentRegistrationValidationError


class MarkdownAgentPackageRegistrationValidator:
    """Accept a markdown package only if it loads and translates."""

    def validate(self, *, application_id: str, request) -> str:
        del application_id

        try:
            bundle = load_agent_definition(request.definition_root)
        except AgentDefinitionError as exc:
            raise AgentRegistrationValidationError(str(exc)) from exc

        if bundle.agent_id != request.agent_id:
            raise AgentRegistrationValidationError(
                "Registered agent ID does not match agent-definition.md"
            )
        if bundle.version != request.version:
            raise AgentRegistrationValidationError(
                "Registered agent version does not match agent-definition.md"
            )

        # Translating now keeps an untranslatable package out of the catalog.
        try:
            translate_bundle(bundle)
        except DefinitionNormalizationError as exc:
            raise AgentRegistrationValidationError(
                f"Agent package cannot be translated: {exc}"
            ) from exc

        return fingerprint_markdown_package(request.definition_root)


def fingerprint_markdown_package(definition_root: Path | str) -> str:
    """Fingerprint the authored files, ignoring line-ending differences."""

    root = Path(definition_root).expanduser().resolve()
    digest = sha256()

    filenames = ["agent.md"] if (root / "agent.md").is_file() else sorted(REQUIRED_DEFINITIONS)
    for filename in filenames:
        path = root / filename
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise AgentRegistrationValidationError(
                f"Cannot read agent definition file: {path}"
            ) from exc
        digest.update(filename.encode())
        digest.update(b"\0")
        digest.update(
            content.replace("\r\n", "\n").replace("\r", "\n").encode()
        )
        digest.update(b"\0")

    return digest.hexdigest()
