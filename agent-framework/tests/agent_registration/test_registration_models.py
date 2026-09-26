"""Tests for bulk registration request models."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

V3_ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"
if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))

from agent_registration import (  # noqa: E402
    AgentRegistrationRequest,
    AgentRegistrationValidationError,
    BulkAgentRegistrationRequest,
)


def agent(agent_id: str = "agent-one", version: str = "1.0"):
    return AgentRegistrationRequest(
        agent_id=agent_id,
        version=version,
        definition_root=Path("prebuilt-agents") / agent_id,
    )


def test_bulk_request_requires_agents() -> None:
    with pytest.raises(
        AgentRegistrationValidationError,
        match="at least one",
    ):
        BulkAgentRegistrationRequest(
            application_id="application-one",
            agents=(),
        )


def test_bulk_request_rejects_duplicate_agent_versions() -> None:
    with pytest.raises(
        AgentRegistrationValidationError,
        match="duplicate",
    ):
        BulkAgentRegistrationRequest(
            application_id="application-one",
            agents=(agent(), agent()),
        )


def test_bulk_request_accepts_multiple_versions() -> None:
    request = BulkAgentRegistrationRequest(
        application_id="application-one",
        agents=(agent(version="1.0"), agent(version="2.0")),
    )
    assert len(request.agents) == 2
