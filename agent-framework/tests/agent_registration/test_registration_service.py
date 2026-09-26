"""Tests for atomic bulk registration."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

V3_ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"
if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))

from agent_registration import (  # noqa: E402
    AgentAlreadyRegisteredError,
    AgentRegistrationKey,
    AgentRegistrationRequest,
    AgentRegistrationService,
    AgentRegistrationValidationError,
    BulkAgentRegistrationRequest,
    InMemoryAgentRegistrationCatalog,
    RegistrationStatus,
)


class FakeValidator:
    def __init__(self, rejected_agent: str | None = None) -> None:
        self.rejected_agent = rejected_agent
        self.calls: list[str] = []

    def validate(self, *, application_id, request) -> str:
        self.calls.append(request.agent_id)
        if request.agent_id == self.rejected_agent:
            raise AgentRegistrationValidationError(
                f"Invalid agent: {request.agent_id}"
            )
        return f"fingerprint:{application_id}:{request.agent_id}:{request.version}"


def registration(agent_id: str, version: str = "1.0"):
    return AgentRegistrationRequest(
        agent_id=agent_id,
        version=version,
        definition_root=Path("prebuilt-agents") / agent_id,
    )


def bulk(*agents):
    return BulkAgentRegistrationRequest(
        application_id="application-one",
        agents=tuple(agents),
    )


def test_registers_complete_batch() -> None:
    catalog = InMemoryAgentRegistrationCatalog()
    service = AgentRegistrationService(catalog, FakeValidator())

    result = service.register_bulk(
        bulk(registration("agent-one"), registration("agent-two"))
    )

    assert result.status is RegistrationStatus.REGISTERED
    assert len(catalog.snapshot()) == 2
    assert len(catalog.list_for_application("application-one")) == 2


def test_validation_failure_commits_nothing() -> None:
    catalog = InMemoryAgentRegistrationCatalog()
    service = AgentRegistrationService(
        catalog,
        FakeValidator(rejected_agent="agent-two"),
    )

    with pytest.raises(AgentRegistrationValidationError):
        service.register_bulk(
            bulk(registration("agent-one"), registration("agent-two"))
        )

    assert catalog.snapshot() == ()


def test_existing_key_rejects_entire_new_batch() -> None:
    catalog = InMemoryAgentRegistrationCatalog()
    service = AgentRegistrationService(catalog, FakeValidator())
    service.register_bulk(bulk(registration("agent-one")))

    with pytest.raises(AgentAlreadyRegisteredError):
        service.register_bulk(
            bulk(registration("agent-two"), registration("agent-one"))
        )

    stored = catalog.snapshot()
    assert len(stored) == 1
    assert stored[0].key.agent_id == "agent-one"


def test_catalog_is_scoped_by_application() -> None:
    catalog = InMemoryAgentRegistrationCatalog()
    validator = FakeValidator()
    service = AgentRegistrationService(catalog, validator)

    service.register_bulk(bulk(registration("agent-one")))

    assert catalog.contains(
        AgentRegistrationKey(
            application_id="application-one",
            agent_id="agent-one",
            version="1.0",
        )
    )
    assert catalog.list_for_application("another-application") == ()
