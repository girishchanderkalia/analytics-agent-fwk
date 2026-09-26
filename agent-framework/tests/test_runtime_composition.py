"""Tests for agent runtime composition."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

V3_ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"
AGENT_REPOSITORY_ROOT = V3_ROOT / "agents"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))

from catalog import AgentCatalog  # noqa: E402
from execution.definition_loader import AgentRepository  # noqa: E402
from host import RuntimeComposer  # noqa: E402


class FakeModelGateway:
    pass


class FakeCapabilityDispatcher:
    pass


class FakeOperationRegistry:
    pass


class FakeContractProvider:
    def get_contract(self, contract_name: str) -> type[Any]:
        return type(contract_name, (), {})


def test_composer_builds_workflow_engine() -> None:
    catalog = AgentCatalog(AgentRepository(AGENT_REPOSITORY_ROOT))
    entry = catalog.resolve("opo-monitoring-agent")

    composer = RuntimeComposer(
        model_gateway_factory=lambda item: FakeModelGateway(),
        capability_dispatcher_factory=(
            lambda item: FakeCapabilityDispatcher()
        ),
        operation_registry_factory=(
            lambda item: FakeOperationRegistry()
        ),
        contract_provider_factory=(
            lambda item: FakeContractProvider()
        ),
        permissions_provider=lambda item: {"query:trends:read"},
        approved_capabilities_provider=lambda item: {"workspace.create"},
    )

    runtime = composer.compose(entry)
    assert runtime.entry is entry
    assert runtime.workflow_engine.bundle is entry.bundle
    assert runtime.execution_context.permissions == frozenset(
        {"query:trends:read"}
    )
