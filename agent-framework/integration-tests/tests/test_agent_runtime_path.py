"""OPO Monitoring front end to Agent Runtime chat path.

The front end never calls the Agent Runtime directly. These tests exercise the
BFF investigation endpoints so a passing run proves the chain
FE -> BFF -> Agent Runtime, including persistence and approval resume.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from e2e.assertions import assert_no_runtime_internals, assert_runtime_response


def chat_request(settings, message: str) -> dict:
    request = {
        "agentId": settings.agent_id,
        "message": message,
        "userId": "e2e-test-user",
        "applicationContext": {"source": "e2e"},
    }
    if settings.agent_version is not None:
        request["agentVersion"] = settings.agent_version
    return request


def require_model_backed_run(settings) -> None:
    if not settings.run_agent_e2e:
        pytest.skip("Set RUN_AGENT_E2E=true for model-backed E2E flow")


@pytest.mark.agent
def test_chat_requires_agent_id_and_message(client, settings):
    response = client.post(
        settings.bff_url + "/api/investigations/chat",
        {"agentId": "  ", "message": ""},
    )

    assert response.status_code == 400


@pytest.mark.agent
def test_unknown_conversation_is_reported_as_downstream_failure(
    client,
    settings,
):
    response = client.get(
        settings.bff_url + "/api/investigations/conversation-does-not-exist"
    )

    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "DOWNSTREAM_ERROR"
    assert body["downstream"] == "runtime-service"


@pytest.mark.agent
def test_resume_of_unknown_conversation_is_reported_as_downstream_failure(
    client,
    settings,
):
    response = client.post(
        settings.bff_url
        + "/api/investigations/conversation-does-not-exist/resume",
        {"approved": True},
    )

    assert response.status_code == 502
    assert response.json()["downstream"] == "runtime-service"


@pytest.mark.agent
def test_chat_is_versioned_and_hides_langgraph_internals(client, settings):
    require_model_backed_run(settings)

    result = client.post_json(
        settings.bff_url + "/api/investigations/chat",
        chat_request(settings, "Show OPO trends for the available test data."),
    )

    assert_runtime_response(result)
    assert result["agentId"] == settings.agent_id
    assert isinstance(result.get("agentVersion"), str)
    assert result["agentVersion"].strip()


@pytest.mark.agent
def test_conversation_can_be_retrieved_through_bff(client, settings):
    require_model_backed_run(settings)

    started = client.post_json(
        settings.bff_url + "/api/investigations/chat",
        chat_request(settings, "Show OPO trends for the available test data."),
    )
    loaded = client.get_json(
        settings.bff_url
        + "/api/investigations/"
        + started["conversationId"]
    )

    assert_runtime_response(loaded)
    assert loaded["conversationId"] == started["conversationId"]
    assert loaded["agentVersion"] == started["agentVersion"]
    assert loaded["version"] >= started["version"]


@pytest.mark.agent
def test_approval_resume_advances_the_conversation(client, settings):
    require_model_backed_run(settings)

    started = client.post_json(
        settings.bff_url + "/api/investigations/chat",
        chat_request(settings, "Investigate the worst overlay outliers."),
    )
    if started["status"] != "waiting_for_approval":
        pytest.skip("Agent did not request approval for this message")

    approval = started["approvalRequest"]
    assert isinstance(approval, Mapping)
    assert_no_runtime_internals(approval)

    resumed = client.post_json(
        settings.bff_url
        + "/api/investigations/"
        + started["conversationId"]
        + "/resume",
        {
            "approved": True,
            "expectedVersion": started["version"],
            "comment": "Approved by end-to-end test",
        },
    )

    assert_runtime_response(resumed)
    assert resumed["conversationId"] == started["conversationId"]
    assert resumed["version"] > started["version"]


@pytest.mark.agent
def test_stale_resume_version_is_rejected(client, settings):
    require_model_backed_run(settings)

    started = client.post_json(
        settings.bff_url + "/api/investigations/chat",
        chat_request(settings, "Investigate the worst overlay outliers."),
    )
    if started["status"] != "waiting_for_approval":
        pytest.skip("Agent did not request approval for this message")

    response = client.post(
        settings.bff_url
        + "/api/investigations/"
        + started["conversationId"]
        + "/resume",
        {"approved": True, "expectedVersion": started["version"] + 99},
    )

    assert response.status_code == 502
    assert response.json()["downstream"] == "runtime-service"
