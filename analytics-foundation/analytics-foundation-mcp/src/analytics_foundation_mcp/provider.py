"""MCP tool backend using the shared Analytics Foundation HTTP client."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Awaitable, Callable

from analytics_foundation_client import (
    AnalyticsFoundationClient,
    DatasetMetadata,
    DistributionStats,
    OutlierDetectionRequest,
    OutlierDetectionResult,
    RegistrationRequest,
    RegistrationStatus,
    TdbbCompareRequest,
    TdbbCompareResult,
    TdbbRunData,
    TdbbRunInfo,
    TdbbRunRequest,
    TdbbRunResult,
    TrendQueryRequest,
    TrendResponse,
    WaferQueryRequest,
    WaferQueryResponse,
    WorkspaceConnectionInfo,
    WorkspaceFiltersRequest,
    WorkspaceFiltersResponse,
    WorkspaceResponse,
)

from .errors import FoundationMcpToolNotFoundError
from .types import FoundationMcpTool, FoundationMcpToolResult

Handler = Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]


class AnalyticsFoundationMcpToolProvider:
    """Expose governed MCP tools backed only by Foundation HTTP APIs."""

    SERVER_ID = "analytics-foundation"

    def __init__(self, client: AnalyticsFoundationClient) -> None:
        self._client = client
        self._handlers: dict[str, Handler] = {
            "query_trends": self._query_trends,
            "get_distribution_stats": self._get_distribution_stats,
            "detect_outliers": self._detect_outliers,
            "get_metadata": self._get_metadata,
            "create_workspace": self._create_workspace,
            "add_workspace_filters": self._add_workspace_filters,
            "get_workspace_connection_info": self._get_workspace_connection_info,
            "register_dataset": self._register_dataset,
            "get_registration_status": self._get_registration_status,
            "query_wafers": self._query_wafers,
            "run_tdbb": self._run_tdbb,
            "compare_tdbb_runs": self._compare_tdbb_runs,
            "get_tdbb_run": self._get_tdbb_run,
            "get_tdbb_data": self._get_tdbb_data,
        }
        self._tools = _tool_catalog()

    async def discover_tools(self) -> tuple[FoundationMcpTool, ...]:
        return self._tools

    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
    ) -> FoundationMcpToolResult:
        try:
            handler = self._handlers[name]
        except KeyError as exc:
            raise FoundationMcpToolNotFoundError(
                f"Unknown Analytics Foundation MCP tool: {name}"
            ) from exc
        content = await handler(dict(arguments))
        return FoundationMcpToolResult(structured_content=content)

    async def _query_trends(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        result = await self._client.query_trends(TrendQueryRequest.model_validate(values))
        return result.model_dump(mode="json")

    async def _get_distribution_stats(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        result = await self._client.get_distribution(TrendQueryRequest.model_validate(values))
        return result.model_dump(mode="json")

    async def _detect_outliers(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        result = await self._client.detect_outliers(OutlierDetectionRequest.model_validate(values))
        return result.model_dump(mode="json")

    async def _get_metadata(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        _require_empty(values)
        result = await self._client.get_metadata()
        return result.model_dump(mode="json")

    async def _create_workspace(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        _require_empty(values)
        result = await self._client.create_workspace()
        return result.model_dump(mode="json")

    async def _add_workspace_filters(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        workspace_id = _required_text(values, "workspace_id")
        request = WorkspaceFiltersRequest.model_validate({"filters": values.get("filters")})
        result = await self._client.add_workspace_filters(workspace_id, request)
        return result.model_dump(mode="json")

    async def _get_workspace_connection_info(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        workspace_id = _required_text(values, "workspace_id")
        _reject_extra(values, {"workspace_id"})
        result = await self._client.get_workspace_connection_info(workspace_id)
        return result.model_dump(mode="json")

    async def _register_dataset(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        workspace_id = _required_text(values, "workspace_id")
        request = RegistrationRequest.model_validate({
            "dataset": values.get("dataset"),
            "table": values.get("table"),
        })
        _reject_extra(values, {"workspace_id", "dataset", "table"})
        result = await self._client.register_dataset(workspace_id, request)
        return result.model_dump(mode="json")

    async def _get_registration_status(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        workspace_id = _required_text(values, "workspace_id")
        registration_id = _required_text(values, "registration_id")
        _reject_extra(values, {"workspace_id", "registration_id"})
        result = await self._client.get_registration_status(workspace_id, registration_id)
        return result.model_dump(mode="json")

    async def _query_wafers(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        result = await self._client.query_wafers(WaferQueryRequest.model_validate(values))
        return result.model_dump(mode="json")

    async def _run_tdbb(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        result = await self._client.run_tdbb(TdbbRunRequest.model_validate(values))
        return result.model_dump(mode="json")

    async def _compare_tdbb_runs(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        _reject_extra(values, {"before_run_ids", "after_run_ids"})
        result = await self._client.compare_tdbb_runs(TdbbCompareRequest.model_validate(values))
        return result.model_dump(mode="json")

    async def _get_tdbb_run(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        run_id = _required_text(values, "run_id")
        _reject_extra(values, {"run_id"})
        result = await self._client.get_tdbb_run(run_id)
        return result.model_dump(mode="json")

    async def _get_tdbb_data(self, values: Mapping[str, Any]) -> Mapping[str, Any]:
        run_id = _required_text(values, "run_id")
        _reject_extra(values, {"run_id", "tables"})
        tables = values.get("tables") or []
        if not isinstance(tables, list) or not all(isinstance(table, str) for table in tables):
            raise ValueError("tables must be a list of strings")
        result = await self._client.get_tdbb_data(run_id, tables)
        return result.model_dump(mode="json")


def _required_text(values: Mapping[str, Any], field: str) -> str:
    value = values.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _require_empty(values: Mapping[str, Any]) -> None:
    if values:
        raise ValueError("tool does not accept arguments")


def _reject_extra(values: Mapping[str, Any], allowed: set[str]) -> None:
    extra = set(values) - allowed
    if extra:
        raise ValueError(f"unsupported arguments: {sorted(extra)}")


def _object_schema(properties: Mapping[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(required or []),
        "additionalProperties": False,
    }


def _trend_schema() -> dict[str, Any]:
    return _object_schema({
        "days": {"type": ["integer", "null"], "minimum": 1, "maximum": 90},
        "start_date": {"type": ["string", "null"]},
        "end_date": {"type": ["string", "null"]},
        "lot_ids": {"type": "array", "items": {"type": "string"}},
        "product_ids": {"type": "array", "items": {"type": "string"}},
        "layer_ids": {"type": "array", "items": {"type": "string"}},
        "exposure_equipment_ids": {"type": "array", "items": {"type": "string"}},
        "chuck_ids": {"type": "array", "items": {"type": "string"}},
    })


def _tdbb_schema() -> dict[str, Any]:
    properties = dict(_trend_schema()["properties"])
    del properties["days"]
    properties.update({
        "start_date": {"type": "string"},
        "end_date": {"type": "string"},
        "change_date": {"type": "string"},
        "model_step": {"type": "string", "enum": ["10par"]},
        "context_levels": {"type": "array", "items": {"type": "string", "enum": ["AVG", "W2W"]}},
    })
    return _object_schema(properties, ["start_date", "end_date", "change_date"])


def _tdbb_compare_schema() -> dict[str, Any]:
    return _object_schema({
        "before_run_ids": {"type": "array", "items": {"type": "string"}},
        "after_run_ids": {"type": "array", "items": {"type": "string"}},
    }, ["before_run_ids", "after_run_ids"])


def _outlier_detection_schema() -> dict[str, Any]:
    properties = dict(_trend_schema()["properties"])
    properties.update({
        "mode": {"type": "string", "enum": ["absolute", "baseline"]},
        "limit_value": {"type": "number"},
        "direction": {"type": "string", "enum": ["above", "below"]},
        "threshold_unit": {"type": "string", "enum": ["percent", "absolute"]},
        "baseline_deviation_pct": {"type": ["number", "null"]},
    })
    return _object_schema(properties)


def _tool_catalog() -> tuple[FoundationMcpTool, ...]:
    empty = _object_schema({})
    return (
        FoundationMcpTool("query_trends", "1", "Query trend series: per-wafer overlay X (kpi_value) and Y (kpi_value_y) KPIs, each |mean| + 3 sigma in nm, grouped by machine, product, lot and layer.", _trend_schema(), TrendResponse.model_json_schema(), {"readOnlyHint": True}),
        FoundationMcpTool("get_distribution_stats", "1", "Get trend distribution statistics (mean, stdev, p95, p99, empirical bell-curve range) for the same trend scope as query_trends.", _trend_schema(), DistributionStats.model_json_schema(), {"readOnlyHint": True}),
        FoundationMcpTool("detect_outliers", "1", "Deterministically find every trend point violating an absolute or per-series baseline threshold; returns each point with its baseline and the applied threshold.", _outlier_detection_schema(), OutlierDetectionResult.model_json_schema(), {"readOnlyHint": True}),
        FoundationMcpTool("get_metadata", "1", "Get the published trend and wafer dataset table names.", empty, DatasetMetadata.model_json_schema(), {"readOnlyHint": True}),
        FoundationMcpTool("create_workspace", "1", "Create a governed analytical workspace for an approved investigation.", empty, WorkspaceResponse.model_json_schema(), {"destructiveHint": False}),
        FoundationMcpTool("add_workspace_filters", "1", "Apply filters to a workspace so only matching rows are registered and queryable.", _object_schema({"workspace_id": {"type": "string"}, "filters": {"type": "object", "additionalProperties": True}}, ["workspace_id", "filters"]), WorkspaceFiltersResponse.model_json_schema(), {"idempotentHint": True}),
        FoundationMcpTool("get_workspace_connection_info", "1", "Get governed connection details for querying a workspace's registered tables directly.", _object_schema({"workspace_id": {"type": "string"}}, ["workspace_id"]), WorkspaceConnectionInfo.model_json_schema(), {"readOnlyHint": True}),
        FoundationMcpTool("register_dataset", "1", "Register a dataset table in a workspace; registration is asynchronous, poll get_registration_status until READY.", _object_schema({"workspace_id": {"type": "string"}, "dataset": {"type": "string"}, "table": {"type": "string"}}, ["workspace_id", "dataset", "table"]), RegistrationStatus.model_json_schema(), {"destructiveHint": False}),
        FoundationMcpTool("get_registration_status", "1", "Get a dataset registration's lifecycle state (PENDING, RUNNING, READY or FAILED) and progress; data is queryable only once READY.", _object_schema({"workspace_id": {"type": "string"}, "registration_id": {"type": "string"}}, ["workspace_id", "registration_id"]), RegistrationStatus.model_json_schema(), {"readOnlyHint": True}),
        FoundationMcpTool("query_wafers", "1", "Query wafer-level rows from a registered workspace table, including which wafers are flagged anomalous.", _object_schema({"workspace_id": {"type": "string"}, "table": {"type": "string"}, "filters": {"type": "object", "additionalProperties": True}}, ["workspace_id", "table"]), WaferQueryResponse.model_json_schema(), {"readOnlyHint": True}),
        FoundationMcpTool("run_tdbb", "1", "Request TDBB processing (10par model, AVG per lot and W2W per wafer context levels) for one period; returns the completed run's NCE and CE wafer/field/translation budgets, each |mean| + 3 sigma in nm, plus per-wafer/per-field maps.", _tdbb_schema(), TdbbRunResult.model_json_schema(), {"destructiveHint": False}),
        FoundationMcpTool("compare_tdbb_runs", "1", "Compare completed TDBB runs by ID and return Foundation-computed before/after budget deltas (nm and percent) and the largest relative increase.", _tdbb_compare_schema(), TdbbCompareResult.model_json_schema(), {"readOnlyHint": True}),
        FoundationMcpTool("get_tdbb_run", "1", "Get a completed TDBB run's metadata: model step, context levels, product/layer/equipment/lot scope and included wafers.", _object_schema({"run_id": {"type": "string"}}, ["run_id"]), TdbbRunInfo.model_json_schema(), {"readOnlyHint": True}),
        FoundationMcpTool("get_tdbb_data", "1", "Get a completed TDBB run's raw output rows for the requested tables (ce_wafer, ce_field, nce_wafer, nce_field).", _object_schema({"run_id": {"type": "string"}, "tables": {"type": "array", "items": {"type": "string", "enum": ["ce_wafer", "ce_field", "nce_wafer", "nce_field"]}}}, ["run_id"]), TdbbRunData.model_json_schema(), {"readOnlyHint": True}),
    )
