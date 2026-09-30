"""Applications register authored markdown packages with the framework."""

from __future__ import annotations

import shutil
import json
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
    register_application_packages_from_environment,
    register_markdown_agents,
    register_markdown_agents_from_environment,
)

AGENT = ROOT / "agents" / "opo-monitoring"
APPLICATION = "opo-monitoring"


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
        APPLICATION, "opo-monitoring-agent", "1.0"
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


def test_overlay_application_is_registered_separately() -> None:
    catalog, _ = register_markdown_agents(application_id=APPLICATION, package_roots=[AGENT])
    register_application_packages_from_environment(
        environment={"AGENT_APPLICATION_PACKAGES": json.dumps({"overlay-data-analysis": [str(ROOT / "agents" / "overlay-analysis")]})},
        catalog=catalog,
    )
    assert [record.key.agent_id for record in catalog.list_for_application(APPLICATION)] == ["opo-monitoring-agent"]
    assert [record.key.agent_id for record in catalog.list_for_application("overlay-data-analysis")] == ["overlay-analysis-agent"]


@pytest.mark.parametrize("raw", ["invalid", "[]", '{"overlay": "path"}', '{"overlay": []}', '{"": ["path"]}'])
def test_invalid_application_package_configuration_is_rejected(raw) -> None:
    catalog, _ = register_markdown_agents_from_environment(application_id=APPLICATION, environment={})
    with pytest.raises(AgentRegistrationValidationError, match="AGENT_APPLICATION_PACKAGES"):
        register_application_packages_from_environment(environment={"AGENT_APPLICATION_PACKAGES": raw}, catalog=catalog)


def test_overlay_chat_runs_in_its_registered_application(tmp_path) -> None:
    from fastapi.testclient import TestClient
    from bootstrap.langgraph_runtime_composition import create_langgraph_conversation_service
    from runtime_api import create_app

    calls = []

    class Model:
        async def invoke_structured(self, system_prompt, input_text, output_contract, tools=None):
            calls.append(input_text)
            assert "conversation_context.overlay" in system_prompt
            assert "MAX_997" in input_text and "3.011" in input_text
            assert not tools
            return output_contract(answer="Lot L1 has X 3.011 and Y 3.458.", limitations=["Units are unspecified."]).model_dump()

    service = create_langgraph_conversation_service(
        environment={
            "AGENT_APPLICATION_ID": APPLICATION,
            "AGENT_MARKDOWN_PACKAGES": str(AGENT),
            "AGENT_APPLICATION_PACKAGES": json.dumps({"overlay-data-analysis": [str(ROOT / "agents" / "overlay-analysis")]}),
            "AGENT_RUNTIME_DATABASE_PATH": str(tmp_path / "conversations.sqlite"),
            "AGENT_RUNTIME_CHECKPOINTER_BACKEND": "memory",
            "ANALYTICS_FOUNDATION_MCP_URL": "http://unused-foundation/mcp",
            "OPO_CAPABILITY_MCP_URL": "http://unused-capability/mcp",
        },
        model_provider=Model(),
    )
    with TestClient(create_app(service)) as client:
        agents = client.get("/v1/applications/overlay-data-analysis/agents").json()["agents"]
        assert [agent["agentId"] for agent in agents] == ["overlay-analysis-agent"]
        request = {
            "applicationId": "overlay-data-analysis", "agentId": "overlay-analysis-agent", "agentVersion": "1.0",
            "message": "Compare X and Y",
            "applicationContext": {"overlay": {"metric": "MAX_997", "filters": {}, "points": [{"lot_id": "L1", "kpi_x": 3.011, "kpi_y": 3.458}]}},
        }
        response = client.post("/v1/chat", json=request)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "completed", body
        assert body["result"]["overlay_analysis"]["answer"] == "Lot L1 has X 3.011 and Y 3.458."
        reopened = client.get(f'/v1/conversations/{body["conversationId"]}').json()
        assert reopened["result"]["overlay_analysis"] == body["result"]["overlay_analysis"]
        assert client.post("/v1/chat", json={**request, "applicationId": APPLICATION}).status_code == 409
        assert len(calls) == 1
