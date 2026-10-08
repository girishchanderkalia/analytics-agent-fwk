"""Applications register authored markdown packages with the framework."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
AGENT_RUNTIME = ROOT / "agent-framework" / "agent-runtime"
if str(AGENT_RUNTIME) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME))

from agent_registration import (  # noqa: E402
    AgentAlreadyRegisteredError,
    AgentRegistrationKey,
    AgentRegistrationValidationError,
    fingerprint_markdown_package,
)
from bootstrap.markdown_agent_registration import (  # noqa: E402
    register_markdown_agents,
    register_markdown_agents_from_environment,
)

AGENT = ROOT / "agents" / "opo-analysis-agent-v1"
APPLICATION = "opo-monitoring"


def test_single_file_v5_registers_alongside_v4() -> None:
    roots = [ROOT / "agents" / f"opo-analysis-agent-{version}" for version in ("v4", "v5")]
    catalog, result = register_markdown_agents(
        application_id=APPLICATION,
        package_roots=roots,
    )
    assert len(result.registrations) == 2
    assert catalog.contains(AgentRegistrationKey(APPLICATION, "opo-analysis-agent-v5", "V5"))


def test_single_file_fingerprint_tracks_knowledge_changes(tmp_path: Path) -> None:
    original = ROOT / "agents" / "opo-analysis-agent-v5"
    target = tmp_path / "v5"
    shutil.copytree(original, target)
    assert fingerprint_markdown_package(target) == fingerprint_markdown_package(original)
    document = target / "agent.md"
    document.write_text(
        document.read_text(encoding="utf-8").replace("Correlation", "Association").replace(
            "Coincident changes", "Simultaneous changes"
        ),
        encoding="utf-8",
    )
    assert fingerprint_markdown_package(target) != fingerprint_markdown_package(original)


def copy_agent(tmp_path: Path) -> Path:
    target = tmp_path / "agent"
    shutil.copytree(AGENT, target)
    return target


def test_registration_reads_identity_from_the_package() -> None:
    catalog, result = register_markdown_agents(
        application_id=APPLICATION,
        package_roots=[AGENT],
    )

    record = result.registrations[0]
    assert record.key == AgentRegistrationKey(
        APPLICATION, "opo-analysis-agent-v1", "V1"
    )
    assert record.definition_root == AGENT.resolve()
    assert catalog.contains(record.key)


def test_catalog_resolves_the_registered_record() -> None:
    catalog, result = register_markdown_agents(
        application_id=APPLICATION,
        package_roots=[AGENT],
    )

    record = catalog.get(result.registrations[0].key)

    assert record.definition_fingerprint
    assert record.definition_root == AGENT.resolve()


def test_fingerprint_is_stable_and_content_addressed(tmp_path: Path) -> None:
    copy = copy_agent(tmp_path)

    assert fingerprint_markdown_package(copy) == fingerprint_markdown_package(AGENT)

    workflow = copy / "workflow-definition.md"
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(
            "Identifying candidate outliers",
            "Finding candidate outliers",
        ),
        encoding="utf-8",
    )

    assert fingerprint_markdown_package(copy) != fingerprint_markdown_package(AGENT)


def test_untranslatable_package_is_refused(tmp_path: Path) -> None:
    copy = copy_agent(tmp_path)
    capabilities = copy / "tools-and-capabilities.md"
    capabilities.write_text(
        capabilities.read_text(encoding="utf-8").replace(
            "    server: analytics-foundation\n    tool: query_trends\n",
            "",
        ),
        encoding="utf-8",
    )

    with pytest.raises(AgentRegistrationValidationError, match="translated"):
        register_markdown_agents(
            application_id=APPLICATION,
            package_roots=[copy],
        )


def test_registering_the_same_version_twice_is_refused() -> None:
    catalog, _ = register_markdown_agents(
        application_id=APPLICATION,
        package_roots=[AGENT],
    )

    with pytest.raises(AgentAlreadyRegisteredError):
        register_markdown_agents(
            application_id=APPLICATION,
            package_roots=[AGENT],
            catalog=catalog,
        )


def test_environment_registration_uses_semicolon_separator() -> None:
    catalog, result = register_markdown_agents_from_environment(
        application_id=APPLICATION,
        environment={"AGENT_MARKDOWN_PACKAGES": str(AGENT)},
    )

    assert result is not None
    assert catalog.contains(result.registrations[0].key)


def test_no_configured_packages_is_a_noop() -> None:
    catalog, result = register_markdown_agents_from_environment(
        application_id=APPLICATION,
        environment={},
    )

    assert result is None
    assert catalog.list_for_application(APPLICATION) == ()
