from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
import httpx
from functools import partial

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parent / "analytics-foundation-client" / "src"))
sys.path.insert(0, str(ROOT.parent / "agent-runtime"))

from analytics_foundation_client import (
    DatasetMetadata,
    DistributionStats,
    OutlierDetectionResult,
    RegistrationStatus,
    TrendResponse,
    TrendSeries,
    TrendPoint,
    FoundationClientError,
    WaferQueryResponse,
    WorkspaceConnectionInfo,
    WorkspaceFiltersResponse,
    WorkspaceResponse,
    TdbbCompareResult,
    TdbbPeriodSummary,
)
from analytics_foundation_mcp import (
    AnalyticsFoundationMcpToolProvider,
    FoundationMcpToolNotFoundError,
)
from analytics_foundation_mcp.registry_bridge import to_registry_descriptors
from mcp_tools import McpToolRegistry


class FakeFoundationClient:
    def __init__(self):
        self.calls = []

    async def query_trends(self, request):
        self.calls.append(("query_trends", request.model_dump()))
        return TrendResponse(series=[])

    async def get_distribution(self, request):
        self.calls.append(("get_distribution", request.model_dump()))
        return DistributionStats(sample_count=0)

    async def detect_outliers(self, request):
        self.calls.append(("detect_outliers", request.model_dump()))
        return OutlierDetectionResult(outliers=[])

    async def get_metadata(self):
        self.calls.append(("get_metadata", {}))
        return DatasetMetadata(trend_table="trend", wafer_table="wafer")

    async def create_workspace(self):
        self.calls.append(("create_workspace", {}))
        return WorkspaceResponse(workspace_id="w-1")

    async def add_workspace_filters(self, workspace_id, request):
        self.calls.append(("add_workspace_filters", workspace_id, request.model_dump()))
        return WorkspaceFiltersResponse(workspace_id=workspace_id, filters=request.filters)

    async def get_workspace_connection_info(self, workspace_id):
        return WorkspaceConnectionInfo(workspace_id=workspace_id, values={})

    async def register_dataset(self, workspace_id, request):
        return RegistrationStatus(registration_id="r-1", workspace_id=workspace_id, status="READY", progress_pct=100, table=request.table)

    async def get_registration_status(self, workspace_id, registration_id):
        return RegistrationStatus(registration_id=registration_id, workspace_id=workspace_id, status="READY", progress_pct=100, table="table")

    async def query_wafers(self, request):
        return WaferQueryResponse(workspace_id=request.workspace_id, table=request.table, rows=[], anomalous_wafers=[])

    async def compare_tdbb_runs(self, request):
        self.calls.append(("compare_tdbb_runs", request.model_dump()))
        return TdbbCompareResult(
            before=TdbbPeriodSummary(period="before", run_ids=request.before_run_ids, lot_count=0, wafer_count=0, budgets=[]),
            after=TdbbPeriodSummary(period="after", run_ids=request.after_run_ids, lot_count=0, wafer_count=0, budgets=[]),
            budgets=[], headline="No TDBB budget increased after the change date.",
        )


def run(awaitable):
    return asyncio.run(awaitable)


def test_discovery_registers_with_existing_registry() -> None:
    provider = AnalyticsFoundationMcpToolProvider(FakeFoundationClient())
    tools = run(provider.discover_tools())
    assert len(tools) == 17
    registry = McpToolRegistry()
    registry.register_many(to_registry_descriptors(tools))
    assert len(registry.snapshot()) == 17
    assert all(item.key.server == "analytics-foundation" for item in registry.snapshot())


def test_trend_tools_use_shared_client_models() -> None:
    client = FakeFoundationClient()
    provider = AnalyticsFoundationMcpToolProvider(client)
    result = run(provider.call_tool("query_trends", {"lotExposureStartFrom": "2026-08-17", "lotIds": ["L1"]}))
    assert result.structured_content == {"rows": [], "rowCount": 0, "truncated": False}
    assert client.calls[0][0] == "query_trends"
    stats = run(provider.call_tool("get_distribution_stats", {}))
    assert stats.structured_content["sample_count"] == 0


def test_workspace_tools_delegate_to_shared_client() -> None:
    client = FakeFoundationClient()
    provider = AnalyticsFoundationMcpToolProvider(client)
    created = run(provider.call_tool("create_workspace", {}))
    assert created.structured_content["workspace_id"] == "w-1"
    filtered = run(provider.call_tool("add_workspace_filters", {"workspace_id": "w-1", "filters": {"machine": "M1"}}))
    assert filtered.structured_content["filters"] == {"machine": "M1"}


def test_registration_and_wafer_tools_delegate() -> None:
    provider = AnalyticsFoundationMcpToolProvider(FakeFoundationClient())
    registration = run(provider.call_tool("register_dataset", {"workspace_id": "w-1", "dataset": "overlay", "table": "wafer"}))
    assert registration.structured_content["status"] == "READY"
    status = run(provider.call_tool("get_registration_status", {"workspace_id": "w-1", "registration_id": "r-1"}))
    assert status.structured_content["registration_id"] == "r-1"
    wafers = run(provider.call_tool("query_wafers", {"workspace_id": "w-1", "table": "wafer", "filters": {}}))
    assert wafers.structured_content["rows"] == []

def test_compare_tool_delegates_run_ids() -> None:
    client = FakeFoundationClient()
    result = run(AnalyticsFoundationMcpToolProvider(client).call_tool("compare_tdbb_runs", {"before_run_ids": ["b"], "after_run_ids": ["a"]}))
    assert result.structured_content["before"]["run_ids"] == ["b"]
    assert client.calls[-1] == ("compare_tdbb_runs", {"before_run_ids": ["b"], "after_run_ids": ["a"]})


def test_unknown_tool_is_rejected() -> None:
    provider = AnalyticsFoundationMcpToolProvider(FakeFoundationClient())
    with pytest.raises(FoundationMcpToolNotFoundError):
        run(provider.call_tool("missing", {}))


def test_strict_arguments_are_enforced() -> None:
    provider = AnalyticsFoundationMcpToolProvider(FakeFoundationClient())
    with pytest.raises(ValueError):
        run(provider.call_tool("create_workspace", {"unexpected": True}))
    with pytest.raises(ValueError):
        run(provider.call_tool("register_dataset", {"workspace_id": "w-1", "dataset": "d", "table": "t", "unexpected": True}))


def test_no_mock_foundation_implementation_imports() -> None:
    source = (ROOT / "src" / "analytics_foundation_mcp" / "provider.py").read_text(encoding="utf-8")
    assert "foundation_api" not in source
    assert "analytics_foundation_clients" not in source


def test_mock_and_jdbc_tools_have_identical_schemas() -> None:
    tools = {tool.name: tool for tool in run(AnalyticsFoundationMcpToolProvider(FakeFoundationClient()).discover_tools())}
    assert tools["query_trends"].input_schema == tools["getWaferLevelKpis"].input_schema
    assert tools["query_trends"].output_schema == tools["getWaferLevelKpis"].output_schema


def test_mock_preserves_metadata_and_matches_lanadb_filter_rounding_and_limits(monkeypatch) -> None:
    class Client(FakeFoundationClient):
        async def query_trends(self, request):
            return TrendResponse(series=[TrendSeries(machine="GW021", product="AAA2", layer_id="L1", lot_id="Lot1", points=[
                TrendPoint(date="2026-09-01T23:59:59.999999Z", kpi_value=2.345, kpi_value_y=1.005,
                           wafer_id="W1", chuck_id=None, measure_process_job_id=42,
                           measurement_equipment_id="MET1", needs_ingestion=True),
                TrendPoint(date="2026-09-01T23:59:59Z", kpi_value=3, kpi_value_y=2,
                           wafer_id="W2", chuck_id=None, measure_process_job_id=43),
                TrendPoint(date="2026-09-02T00:00:00Z", kpi_value=99, kpi_value_y=99),
                TrendPoint(date="2026-09-01T00:00:00Z", kpi_value=99, kpi_value_y=None),
            ])])

    monkeypatch.setenv("LANADB_MAX_ROWS", "1")
    args = {"lotExposureStartFrom": "2026-09-01", "lotExposureStartTo": "2026-09-01",
            "productIds": ["AAA2", None], "layerIds": ["L1"], "lotIds": ["Lot1"],
            "exposureEquipmentIds": ["GW021"], "chuckIds": [None]}
    result = run(AnalyticsFoundationMcpToolProvider(Client()).call_tool("query_trends", args)).structured_content
    assert result["rowCount"] == 1 and result["truncated"] is True
    row = result["rows"][0]
    assert row["kpiValue1"] == 2.35 and row["kpiValue2"] == 1.01
    assert row["measureProcessJobId"] == 42 and row["measurementEquipmentId"] == "MET1"
    assert row["needsIngestion"] is True and row["chuckId"] is None
    args["productIds"] = [None]
    assert run(AnalyticsFoundationMcpToolProvider(Client()).call_tool("query_trends", args)).structured_content["rows"] == []


def test_jdbc_forwarding_preserves_arguments_and_result(monkeypatch) -> None:
    args = {"lotExposureStartFrom": "2026-08-17", "chuckIds": [None]}
    expected = {"rows": [], "rowCount": 0, "truncated": False}

    def handle(request):
        import json
        payload = json.loads(request.content)
        assert payload["params"] == {"name": "getWaferLevelKpis", "arguments": args}
        assert str(request.url) == "http://jdbc.test/mcp"
        return httpx.Response(200, json={"result": {"structuredContent": expected, "isError": False}})

    monkeypatch.setenv("LANADB_MCP_URL", "http://jdbc.test/mcp")
    monkeypatch.setattr(httpx, "AsyncClient", partial(httpx.AsyncClient, transport=httpx.MockTransport(handle)))
    result = run(AnalyticsFoundationMcpToolProvider(FakeFoundationClient()).call_tool("getWaferLevelKpis", args))
    assert result.structured_content == expected


def test_jdbc_errors_do_not_fall_back_to_mock_or_leak_details(monkeypatch) -> None:
    monkeypatch.setenv("LANADB_MCP_URL", "http://jdbc.test/mcp")
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"error": {"message": "secret"}}))
    monkeypatch.setattr(httpx, "AsyncClient", partial(httpx.AsyncClient, transport=transport))
    client = FakeFoundationClient()
    with pytest.raises(FoundationClientError, match="JDBC wafer KPI tool failed"):
        run(AnalyticsFoundationMcpToolProvider(client).call_tool("getWaferLevelKpis", {"lotExposureStartFrom": "2026-08-17"}))
    assert client.calls == []


def test_deterministic_tdbb_report_selects_full_periods_and_has_four_bullets():
    from analytics_foundation_mcp.tdbb_evidence import TdbbEvidenceRequest, summarize_tdbb_evidence

    def period(name, end, count, value):
        return {"period": name, "start_date": "2026-08-17" if name == "before" else "2026-09-01",
                "end_date": end, "run_ids": [], "lot_count": count, "wafer_count": count * 4,
                "budgets": [{"budget": "nce_wafer.average", "label": "NCE Wafer Average", "metric": "nce_wafer",
                             "metric_label": "NCE Wafer", "context": "average", "context_label": "Average",
                             "x_m3s": value, "y_m3s": value}]}
    before = period("before", "2026-08-31", 30, 1)
    wrong_after = period("after", "2026-09-01", 2, 99)
    after = period("after", "2026-10-09", 60, 2)
    args = {"before_periods": [wrong_after, before], "after_periods": [after, before], "section": "summary"}
    first = summarize_tdbb_evidence(TdbbEvidenceRequest.model_validate(args))
    second = summarize_tdbb_evidence(TdbbEvidenceRequest.model_validate(args))
    assert first == second
    assert "60 lots / 240 wafers" in first.message and "2 lots / 8 wafers" not in first.message
    assert [line.split(":", 1)[0] for line in first.message.splitlines()[1:]] == [
        "- Average", "- Chuck to chuck", "- Lot to lot", "- Wafer to wafer"]
    assert "+100.0%" in first.message


def test_deterministic_nce_report_checks_ce_growth_and_separates_sections():
    from analytics_foundation_mcp.tdbb_evidence import TdbbEvidenceRequest, summarize_tdbb_evidence

    def period(name, value, center, edge):
        return {"period": name, "start_date": "2026-08-17" if name == "before" else "2026-09-01",
                "end_date": "2026-08-31" if name == "before" else "2026-10-09",
                "run_ids": [], "lot_count": 30, "wafer_count": 120,
                "budgets": [{"budget": metric + ".average", "label": metric, "metric": metric,
                             "metric_label": metric, "context": "average", "context_label": "Average",
                             "x_m3s": value, "y_m3s": value} for metric in ("nce_wafer", "ce_wafer")],
                "radial_profile": {"nce_wafer.average": [{"band": "center", "x_m3s": center, "y_m3s": center},
                                                {"band": "edge", "x_m3s": edge, "y_m3s": edge}]}}
    args = {"before_periods": [period("before", 1, 1, 1)],
            "after_periods": [period("after", 2, 1.5, 3)], "section": "nce"}
    result = summarize_tdbb_evidence(TdbbEvidenceRequest.model_validate(args))
    assert "CE wafer budgets also increased" in result.message
    assert "not exclusively non-correctable" in result.message
    assert "disproportionate" in result.message
    assert len(result.recommended_next_actions) == 3
    assert "Recommendations:" not in result.message
    assert "Limitations:" not in result.message
    assert result.correlated_evidence and result.limitations
    assert result == summarize_tdbb_evidence(TdbbEvidenceRequest.model_validate(args))
    args["before_periods"][0]["lot_count"] = 0
    empty = summarize_tdbb_evidence(TdbbEvidenceRequest.model_validate(args))
    assert "comparable" in " ".join(empty.limitations)
    assert empty.recommended_next_actions == []


def test_tdbb_report_rejects_missing_duplicate_or_overlapping_periods():
    from analytics_foundation_mcp.tdbb_evidence import TdbbEvidenceRequest, summarize_tdbb_evidence

    before = {"period": "before", "start_date": "2026-08-17", "end_date": "2026-08-31",
              "run_ids": [], "lot_count": 1, "wafer_count": 1, "budgets": []}
    after = {**before, "period": "after", "start_date": "2026-09-01", "end_date": "2026-09-30"}
    for selected in ([], [before, before]):
        with pytest.raises(ValueError, match="exactly one"):
            summarize_tdbb_evidence(TdbbEvidenceRequest.model_validate({
                "before_periods": selected, "after_periods": [after], "section": "summary"}))
    after["start_date"] = "2026-08-31"
    with pytest.raises(ValueError, match="overlap"):
        summarize_tdbb_evidence(TdbbEvidenceRequest.model_validate({
            "before_periods": [before], "after_periods": [after], "section": "summary"}))


def test_tdbb_report_does_not_fabricate_percentage_from_zero_baseline():
    from analytics_foundation_mcp.tdbb_evidence import TdbbEvidenceRequest, summarize_tdbb_evidence

    budget = {"budget": "nce_wafer.average", "label": "NCE Wafer Average", "metric": "nce_wafer",
              "metric_label": "NCE Wafer", "context": "average", "context_label": "Average",
              "x_m3s": 0, "y_m3s": None}
    before = {"period": "before", "start_date": "2026-08-17", "end_date": "2026-08-31",
              "run_ids": [], "lot_count": 1, "wafer_count": 1, "budgets": [budget]}
    after = {**before, "period": "after", "start_date": "2026-09-01", "end_date": "2026-09-30",
             "budgets": [{**budget, "x_m3s": 3}]}
    result = summarize_tdbb_evidence(TdbbEvidenceRequest.model_validate({
        "before_periods": [before], "after_periods": [after], "section": "summary"}))
    assert "0 to 3 nm (percentage change undefined)" in result.message
    assert "undefined" in " ".join(result.limitations)


def test_tdbb_zero_budgets_are_not_reported_as_missing_evidence():
    from analytics_foundation_mcp.tdbb_evidence import TdbbEvidenceRequest, summarize_tdbb_evidence

    budget = {"budget": "nce_wafer.chuck_to_chuck", "label": "NCE Wafer Chuck to chuck", "metric": "nce_wafer",
              "metric_label": "NCE Wafer", "context": "chuck_to_chuck", "context_label": "Chuck to chuck",
              "x_m3s": 0, "y_m3s": 0}
    before = {"period": "before", "start_date": "2026-08-17", "end_date": "2026-08-31",
              "run_ids": [], "lot_count": 1, "wafer_count": 1, "budgets": [budget]}
    after = {**before, "period": "after", "start_date": "2026-09-01", "end_date": "2026-09-30"}
    result = summarize_tdbb_evidence(TdbbEvidenceRequest.model_validate({
        "before_periods": [before], "after_periods": [after], "section": "summary"}))
    assert "- Chuck to chuck: unchanged zero budgets" in result.message
    assert result.limitations == []
