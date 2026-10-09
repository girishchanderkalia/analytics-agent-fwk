from __future__ import annotations

import pytest


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
        "getWaferLevelKpis",
        "summarize_tdbb_evidence",
        "get_distribution_stats",
        "get_metadata",
        "create_workspace",
        "add_workspace_filters",
        "register_dataset",
        "get_registration_status",
        "query_wafers",
    } <= names


@pytest.mark.smoke
def test_wafer_kpi_tools_publish_identical_contracts(client, settings):
    response = client.post_json(settings.foundation_mcp_url + "/mcp", {
        "jsonrpc": "2.0", "id": "wafer-contract", "method": "tools/list", "params": {},
    })
    tools = {tool["name"]: tool for tool in response["result"]["tools"]}
    assert tools["query_trends"]["inputSchema"] == tools["getWaferLevelKpis"]["inputSchema"]
    assert tools["query_trends"]["outputSchema"] == tools["getWaferLevelKpis"]["outputSchema"]
    for name in ("query_trends", "getWaferLevelKpis"):
        response = client.post_json(settings.foundation_mcp_url + "/mcp", {
            "jsonrpc": "2.0", "id": name, "method": "tools/call",
            "params": {"name": name, "arguments": {
                "lotExposureStartFrom": "1990-01-01", "lotExposureStartTo": "1990-01-02",
                "productIds": ["__no_such_product__"],
            }},
        })
        assert response["result"]["isError"] is False
        assert response["result"]["structuredContent"] == {"rows": [], "rowCount": 0, "truncated": False}


@pytest.mark.smoke
def test_mock_and_jdbc_have_identical_deterministic_tdbb_reports(client, settings):
    def call(name, arguments):
        response = client.post_json(settings.foundation_mcp_url + "/mcp", {
            "jsonrpc": "2.0", "id": name, "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        assert "error" not in response, response.get("error")
        assert response["result"]["isError"] is False
        return response["result"]["structuredContent"]

    arguments = {"lotExposureStartFrom": "2026-08-17", "lotExposureStartTo": "2026-10-09",
                 "productIds": ["AAA2"], "layerIds": ["OV_NO_ID2"],
                 "exposureEquipmentIds": ["GW021"], "chuckIds": ["Waferstage chuck ID 1"]}
    scope = {"start_date": "2026-08-17", "end_date": "2026-10-09", "change_date": "2026-09-01",
             "product_ids": arguments["productIds"], "layer_ids": arguments["layerIds"],
             "exposure_equipment_ids": arguments["exposureEquipmentIds"], "chuck_ids": arguments["chuckIds"]}
    results = []
    for tool in ("query_trends", "getWaferLevelKpis"):
        trends = call(tool, arguments)
        assert trends["rowCount"] > 0 and trends["truncated"] is False
        before = call("run_tdbb", {**scope, "end_date": scope["change_date"]})
        after = call("run_tdbb", scope)
        reports = {}
        for section in ("overview", "summary", "nce"):
            reports[section] = call("summarize_tdbb_evidence", {
                "before_periods": before["periods"], "after_periods": after["periods"], "section": section,
            })
        results.append((trends, before, after, reports))
    left, right = results
    for trends in (left[0], right[0]):
        trends["rows"] = [{key: value for key, value in row.items() if key != "measureProcessJobId"}
                          for row in trends["rows"]]
    assert left == right
    assert len(left[3]["summary"]["message"].splitlines()) == 5
    assert "CE wafer budgets also increased" in left[3]["nce"]["message"]
    assert "disproportionate" in left[3]["nce"]["message"]
    assert len(left[3]["nce"]["recommended_next_actions"]) == 3
    assert any("radial edge" in item for item in left[3]["nce"]["correlated_evidence"])
