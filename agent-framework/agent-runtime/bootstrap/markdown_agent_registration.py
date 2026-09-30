"""Register authored markdown agent packages with the framework catalog.

Applications supply their package roots and own the application identity; the
framework owns validation, fingerprinting, and the catalog.
"""

from __future__ import annotations

import os
import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from agent_registration import (
    AgentRegistrationRequest,
    AgentRegistrationService,
    AgentRegistrationValidationError,
    BulkAgentRegistrationRequest,
    BulkAgentRegistrationResult,
    InMemoryAgentRegistrationCatalog,
    MarkdownAgentPackageRegistrationValidator,
)
from execution.definition_loader import (
    AgentDefinitionError,
    load_agent_definition,
)

PACKAGES_VARIABLE = "AGENT_MARKDOWN_PACKAGES"
APPLICATION_PACKAGES_VARIABLE = "AGENT_APPLICATION_PACKAGES"


def register_application_packages_from_environment(
    *,
    environment: Mapping[str, str],
    catalog: InMemoryAgentRegistrationCatalog,
) -> InMemoryAgentRegistrationCatalog:
    raw = environment.get(APPLICATION_PACKAGES_VARIABLE, "").strip()
    if not raw:
        return catalog
    try:
        applications = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgentRegistrationValidationError(
            f"{APPLICATION_PACKAGES_VARIABLE} must be a JSON object of application IDs to package-path lists"
        ) from exc
    if not isinstance(applications, dict) or any(
        not isinstance(identity, str) or not identity.strip()
        or not isinstance(roots, list) or not roots
        or any(not isinstance(root, str) or not root.strip() for root in roots)
        for identity, roots in applications.items()
    ):
        raise AgentRegistrationValidationError(
            f"{APPLICATION_PACKAGES_VARIABLE} must be a JSON object of application IDs to nonempty package-path lists"
        )
    for identity, roots in applications.items():
        register_markdown_agents(application_id=identity, package_roots=roots, catalog=catalog)
    return catalog


def register_markdown_agents(
    *,
    application_id: str,
    package_roots: Iterable[Path | str],
    catalog: InMemoryAgentRegistrationCatalog | None = None,
) -> tuple[InMemoryAgentRegistrationCatalog, BulkAgentRegistrationResult]:
    """Validate and register every supplied markdown package atomically."""

    roots = [Path(root).expanduser().resolve() for root in package_roots]
    if not roots:
        raise AgentRegistrationValidationError(
            "At least one agent package root is required"
        )

    target = catalog or InMemoryAgentRegistrationCatalog()
    service = AgentRegistrationService(
        target,
        MarkdownAgentPackageRegistrationValidator(),
    )

    result = service.register_bulk(
        BulkAgentRegistrationRequest(
            application_id=application_id,
            agents=tuple(_request(root) for root in roots),
        )
    )
    return target, result


def register_markdown_agents_from_environment(
    *,
    application_id: str,
    environment: Mapping[str, str] | None = None,
    catalog: InMemoryAgentRegistrationCatalog | None = None,
    variable: str = PACKAGES_VARIABLE,
) -> tuple[InMemoryAgentRegistrationCatalog, BulkAgentRegistrationResult | None]:
    """Register packages listed in a semicolon-separated variable."""

    env = dict(os.environ if environment is None else environment)
    raw = env.get(variable, "").strip()

    if not raw:
        return catalog or InMemoryAgentRegistrationCatalog(), None

    roots = [value.strip() for value in raw.split(";") if value.strip()]
    return register_markdown_agents(
        application_id=application_id,
        package_roots=roots,
        catalog=catalog,
    )


def _request(root: Path) -> AgentRegistrationRequest:
    """Read identity from the package so callers do not restate it."""

    try:
        bundle = load_agent_definition(root)
    except AgentDefinitionError as exc:
        raise AgentRegistrationValidationError(str(exc)) from exc

    return AgentRegistrationRequest(
        agent_id=bundle.agent_id,
        version=bundle.version,
        definition_root=root,
    )
