"""OPO Monitoring front end to Analytics Foundation deterministic path.

Every request goes through the public BFF contract the front end consumes, so
a passing run proves the whole chain FE -> BFF -> Analytics Foundation.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest


DEFAULT_FILTERS = {
    "days": 14,
    "lotIds": [],
    "productIds": [],
    "layerIds": [],
    "exposureEquipmentIds": [],
}


@pytest.mark.deterministic
def test_trend_query_returns_series_contract(client, settings):
    result = client.post_json(
        settings.bff_url + "/api/trends/query",
        {"filters": DEFAULT_FILTERS, "groupBy": []},
    )

    assert isinstance(result["series"], list)
    for series in result["series"]:
        assert isinstance(series["machine"], str)
        assert isinstance(series["product"], str)
        assert isinstance(series["points"], list)
        for point in series["points"]:
            assert isinstance(point["date"], str)
            assert isinstance(point["kpi_value"], (int, float))


@pytest.mark.deterministic
def test_trend_query_accepts_snake_case_filters(client, settings):
    result = client.post_json(
        settings.bff_url + "/api/trends/query",
        {
            "filters": {
                "days": 7,
                "lot_ids": [],
                "product_ids": [],
                "layer_ids": [],
                "exposure_equipment_ids": [],
            },
            "groupBy": [],
        },
    )

    assert isinstance(result["series"], list)


@pytest.mark.deterministic
def test_trend_query_rejects_out_of_range_window(client, settings):
    response = client.post(
        settings.bff_url + "/api/trends/query",
        {"filters": {"days": 5000}, "groupBy": []},
    )

    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "DOWNSTREAM_ERROR"
    assert body["downstream"] == "analytics-foundation"


@pytest.mark.deterministic
def test_distribution_returns_statistics_contract(client, settings):
    result = client.post_json(
        settings.bff_url + "/api/trends/distribution",
        {"filters": DEFAULT_FILTERS, "metric": "opo"},
    )

    assert isinstance(result["count"], int)
    assert result["count"] >= 0
    quantiles = result["quantiles"]
    assert isinstance(quantiles, Mapping)
    assert set(quantiles) == {"p95", "p99", "stdev", "bell_curve_range"}
    if result["count"] == 0:
        assert result["mean"] is None
        assert quantiles["p95"] is None
    else:
        assert isinstance(result["mean"], (int, float))
        assert isinstance(quantiles["p95"], (int, float))


@pytest.mark.deterministic
def test_workspace_lifecycle_through_bff(client, settings):
    created = client.post_json(
        settings.bff_url + "/api/workspaces",
        {"name": "e2e-workspace", "context": {"source": "e2e"}},
    )
    workspace_id = created["workspaceId"]
    assert isinstance(workspace_id, str) and workspace_id.strip()

    filtered = client.post_json(
        settings.bff_url + f"/api/workspaces/{workspace_id}/filters",
        {"filters": {"lot_id": "LOT-1"}},
    )
    assert filtered["workspaceId"] == workspace_id

    connection = client.get_json(
        settings.bff_url + f"/api/workspaces/{workspace_id}/connection-info"
    )
    assert connection["workspaceId"] == workspace_id
    assert isinstance(connection["connectionInfo"], Mapping)

    registered = client.post_json(
        settings.bff_url + f"/api/workspaces/{workspace_id}/registrations",
        {"dataset": "overlay", "table": "overlay_wafer_points"},
    )
    registration_id = registered["registrationId"]
    assert isinstance(registration_id, str) and registration_id.strip()
    assert registered["workspaceId"] == workspace_id
    assert registered["table"] == "overlay_wafer_points"
    assert registered["status"] in {"PENDING", "RUNNING", "READY", "FAILED"}
    assert 0 <= registered["progressPct"] <= 100

    loaded = client.get_json(
        settings.bff_url
        + f"/api/workspaces/{workspace_id}/registrations/{registration_id}"
    )
    assert loaded["registrationId"] == registration_id
    assert loaded["status"] == registered["status"]


@pytest.mark.deterministic
def test_wafer_query_through_bff(client, settings):
    created = client.post_json(
        settings.bff_url + "/api/workspaces",
        {"name": "e2e-wafer-workspace", "context": {}},
    )
    workspace_id = created["workspaceId"]

    result = client.post_json(
        settings.bff_url + "/api/wafers/query",
        {
            "workspaceId": workspace_id,
            "table": "overlay_wafer_points",
            "filters": {},
        },
    )

    assert result["workspaceId"] == workspace_id
    assert result["table"] == "overlay_wafer_points"
    assert isinstance(result["rows"], list)
    assert isinstance(result["anomalousWafers"], list)
    for wafer_id in result["anomalousWafers"]:
        assert isinstance(wafer_id, str)


@pytest.mark.deterministic
def test_wafer_query_for_unknown_workspace_is_a_downstream_failure(
    client,
    settings,
):
    response = client.post(
        settings.bff_url + "/api/wafers/query",
        {
            "workspaceId": "workspace-does-not-exist",
            "table": "overlay_wafer_points",
            "filters": {},
        },
    )

    assert response.status_code == 502
    assert response.json()["downstream"] == "analytics-foundation"


@pytest.mark.deterministic
def test_unknown_workspace_is_reported_as_downstream_failure(
    client,
    settings,
):
    response = client.get(
        settings.bff_url
        + "/api/workspaces/workspace-does-not-exist/connection-info"
    )

    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "DOWNSTREAM_ERROR"
    assert body["downstream"] == "analytics-foundation"


@pytest.mark.deterministic
def test_deterministic_path_never_exposes_agent_state(client, settings):
    result = client.post_json(
        settings.bff_url + "/api/trends/query",
        {"filters": DEFAULT_FILTERS, "groupBy": []},
    )

    assert "conversationId" not in result
    assert "approvalRequest" not in result
