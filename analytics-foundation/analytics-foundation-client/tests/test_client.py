from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from analytics_foundation_client import (
    AnalyticsFoundationClient,
    AnalyticsFoundationClientSettings,
    FoundationConnectionError,
    FoundationHttpError,
    FoundationResponseError,
    RegistrationRequest,
    TrendQueryRequest,
    WaferQueryRequest,
    WorkspaceFiltersRequest,
)


def run(awaitable):
    return asyncio.run(awaitable)


def client(handler):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(
        base_url="http://foundation.test",
        transport=transport,
    )
    return AnalyticsFoundationClient(
        AnalyticsFoundationClientSettings("http://foundation.test"),
        http_client=http_client,
    ), http_client


def test_health_and_metadata_are_validated() -> None:
    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={"trend_table": "trend", "wafer_table": "wafer"},
        )

    value, http_client = client(handler)
    try:
        assert run(value.health()).status == "ok"
        assert run(value.get_metadata()).wafer_table == "wafer"
    finally:
        run(http_client.aclose())


def test_display_trends_uses_repeated_list_query_parameters() -> None:
    captured = {}

    def handler(request):
        captured["query"] = request.url.query.decode()
        return httpx.Response(200, json={"series": []})

    value, http_client = client(handler)
    try:
        result = run(
            value.get_display_trends(
                TrendQueryRequest(days=14, lot_ids=["L1", "L2"])
            )
        )
        assert result.series == []
        assert "days=14" in captured["query"]
        assert captured["query"].count("lot_ids=") == 2
    finally:
        run(http_client.aclose())


def test_post_operations_match_foundation_contract() -> None:
    captured = []

    def handler(request):
        body = json.loads(request.content or b"{}")
        captured.append((request.method, request.url.path, body))
        if request.url.path == "/trends/query":
            return httpx.Response(200, json={"series": []})
        if request.url.path == "/trends/distribution":
            return httpx.Response(200, json={"sample_count": 0})
        if request.url.path == "/workspaces":
            return httpx.Response(201, json={"workspace_id": "workspace-1"})
        if request.url.path.endswith("/filters"):
            return httpx.Response(
                200,
                json={"workspace_id": "workspace-1", "filters": body["filters"]},
            )
        if request.url.path.endswith("/registrations"):
            return httpx.Response(
                202,
                json={
                    "registration_id": "registration-1",
                    "workspace_id": "workspace-1",
                    "status": "READY",
                    "progress_pct": 100,
                    "table": body["table"],
                    "error": None,
                },
            )
        return httpx.Response(
            200,
            json={
                "workspace_id": "workspace-1",
                "table": "wafer",
                "rows": [],
                "anomalous_wafers": [],
            },
        )

    value, http_client = client(handler)
    try:
        run(value.query_trends(TrendQueryRequest()))
        run(value.get_distribution(TrendQueryRequest()))
        assert run(value.create_workspace()).workspace_id == "workspace-1"
        run(
            value.add_workspace_filters(
                "workspace-1",
                WorkspaceFiltersRequest(filters={"machine": "M1"}),
            )
        )
        run(
            value.register_dataset(
                "workspace-1",
                RegistrationRequest(dataset="overlay", table="wafer"),
            )
        )
        run(
            value.query_wafers(
                WaferQueryRequest(
                    workspace_id="workspace-1",
                    table="wafer",
                )
            )
        )
        assert ("POST", "/trends/query", {
            "days": None,
            "start_date": None,
            "end_date": None,
            "lot_ids": [],
            "product_ids": [],
            "layer_ids": [],
            "exposure_equipment_ids": [],
        }) in captured
    finally:
        run(http_client.aclose())


def test_http_error_preserves_status_and_safe_body() -> None:
    def handler(request):
        return httpx.Response(404, json={"detail": "missing"})

    value, http_client = client(handler)
    try:
        with pytest.raises(FoundationHttpError) as captured:
            run(value.get_workspace_connection_info("missing"))
        assert captured.value.status_code == 404
        assert captured.value.response_body == {"detail": "missing"}
    finally:
        run(http_client.aclose())


def test_invalid_success_response_is_rejected() -> None:
    value, http_client = client(
        lambda request: httpx.Response(200, json={"unexpected": True})
    )
    try:
        with pytest.raises(FoundationResponseError):
            run(value.health())
    finally:
        run(http_client.aclose())


def test_transport_error_is_mapped() -> None:
    def handler(request):
        raise httpx.ConnectError("offline", request=request)

    value, http_client = client(handler)
    try:
        with pytest.raises(FoundationConnectionError):
            run(value.ready())
    finally:
        run(http_client.aclose())


def test_path_identifiers_are_encoded() -> None:
    captured = {}

    def handler(request):
        captured["path"] = request.url.raw_path.decode()
        return httpx.Response(
            200,
            json={"workspace_id": "a/b", "values": {}},
        )

    value, http_client = client(handler)
    try:
        run(value.get_workspace_connection_info("a/b"))
        assert captured["path"] == "/workspaces/a%2Fb/connection-info"
    finally:
        run(http_client.aclose())
