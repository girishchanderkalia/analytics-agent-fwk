from __future__ import annotations

import pytest

from e2e.assertions import assert_runtime_response


@pytest.mark.agent
def test_chat_is_versioned_and_hides_langgraph_internals(
    client,
    settings,
):
    if not settings.run_agent_e2e:
        pytest.skip("Set RUN_AGENT_E2E=true for model-backed E2E flow")

    request = {
        "agentId": settings.agent_id,
        "message": "Show OPO trends for the available test data.",
        "userId": "slice-13k-test-user",
        "applicationContext": {
            "source": "slice-13k",
        },
    }
    if settings.agent_version is not None:
        request["agentVersion"] = settings.agent_version

    result = client.post_json(
        settings.bff_url + "/api/investigations/chat",
        request,
    )
    assert_runtime_response(result)
    assert result["agentId"] == settings.agent_id
    assert isinstance(result.get("agentVersion"), str)
    assert result["agentVersion"].strip()


@pytest.mark.agent
def test_conversation_can_be_retrieved_through_bff(client, settings):
    if not settings.run_agent_e2e:
        pytest.skip("Set RUN_AGENT_E2E=true for model-backed E2E flow")

    started = client.post_json(
        settings.bff_url + "/api/investigations/chat",
        {
            "agentId": settings.agent_id,
            "agentVersion": settings.agent_version,
            "message": "Show OPO trends for the available test data.",
            "applicationContext": {"source": "slice-13k"},
        },
    )
    loaded = client.get_json(
        settings.bff_url
        + "/api/investigations/"
        + started["conversationId"]
    )
    assert_runtime_response(loaded)
    assert loaded["conversationId"] == started["conversationId"]
    assert loaded["agentVersion"] == started["agentVersion"]
