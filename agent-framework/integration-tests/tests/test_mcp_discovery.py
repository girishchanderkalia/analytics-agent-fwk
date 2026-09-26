from __future__ import annotations

import pytest


@pytest.mark.smoke
def test_opo_tool_catalog_matches_agent_package(client, settings):
    response = client.post_json(
        settings.opo_capability_url + "/mcp",
        {
            "jsonrpc": "2.0",
            "id": "opo-list",
            "method": "tools/list",
            "params": {},
        },
    )
    tools = response["result"]["tools"]
    assert {item["name"] for item in tools} == {
        "analyze_trends",
        "normalize_wafer_evidence",
        "classify_spatial_pattern",
    }


@pytest.mark.smoke
def test_foundation_mcp_exposes_required_tools(client, settings):
    response = client.post_json(
        settings.foundation_mcp_url + "/mcp",
        {
            "jsonrpc": "2.0",
            "id": "foundation-list",
            "method": "tools/list",
            "params": {},
        },
    )
    names = {
        item["name"]
        for item in response["result"]["tools"]
    }
    assert {
        "query_trends",
        "get_distribution_stats",
        "get_metadata",
        "create_workspace",
        "add_workspace_filters",
        "register_dataset",
        "get_registration_status",
        "query_wafers",
    } <= names
