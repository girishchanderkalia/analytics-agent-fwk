"""Tests for the declarative agent catalog."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

V3_ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"
AGENT_REPOSITORY_ROOT = V3_ROOT / "agents"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))

from catalog import AgentCatalog, AgentNotFoundError  # noqa: E402
from execution.definition_loader import AgentRepository  # noqa: E402


def create_catalog() -> AgentCatalog:
    return AgentCatalog(AgentRepository(AGENT_REPOSITORY_ROOT))


def test_catalog_discovers_opo_agent() -> None:
    catalog = create_catalog()
    catalog.refresh()
    assert catalog.contains("opo-monitoring-agent", "1.0")


def test_catalog_resolves_agent() -> None:
    entry = create_catalog().resolve("opo-monitoring-agent")
    assert entry.agent_id == "opo-monitoring-agent"
    assert entry.version == "1.0"
    assert entry.directory_name == "opo-monitoring"


def test_catalog_lists_agent_metadata() -> None:
    items = create_catalog().list()
    assert any(item["agent_id"] == "opo-monitoring-agent" for item in items)


def test_unknown_agent_is_rejected() -> None:
    with pytest.raises(AgentNotFoundError, match="not available"):
        create_catalog().resolve("unknown-agent")


def test_unknown_version_is_rejected() -> None:
    with pytest.raises(AgentNotFoundError, match="version is not available"):
        create_catalog().resolve("opo-monitoring-agent", "999.0")
