"""MCP tool backend using the shared Analytics Foundation HTTP client."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Awaitable, Callable

from analytics_foundation_client import (
    AnalyticsFoundationClient,
    TdbbCompareRequest,
    RegistrationRequest,
    TdbbRunRequest,
    TrendQueryRequest,
    WaferQueryRequest,
    WorkspaceFiltersRequest,
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


def _tool_catalog() -> tuple[FoundationMcpTool, ...]:
    any_object = {"type": "object", "additionalProperties": True}
    empty = _object_schema({})
    return (
        FoundationMcpTool("query_trends", "1", "Query trend series.", _trend_schema(), any_object, {"readOnlyHint": True}),
        FoundationMcpTool("get_distribution_stats", "1", "Get trend distribution statistics.", _trend_schema(), any_object, {"readOnlyHint": True}),
        FoundationMcpTool("get_metadata", "1", "Get dataset metadata.", empty, any_object, {"readOnlyHint": True}),
        FoundationMcpTool("create_workspace", "1", "Create a workspace.", empty, any_object, {"destructiveHint": False}),
        FoundationMcpTool("add_workspace_filters", "1", "Apply workspace filters.", _object_schema({"workspace_id": {"type": "string"}, "filters": any_object}, ["workspace_id", "filters"]), any_object, {"idempotentHint": True}),
        FoundationMcpTool("get_workspace_connection_info", "1", "Get workspace connection information.", _object_schema({"workspace_id": {"type": "string"}}, ["workspace_id"]), any_object, {"readOnlyHint": True}),
        FoundationMcpTool("register_dataset", "1", "Register a dataset in a workspace.", _object_schema({"workspace_id": {"type": "string"}, "dataset": {"type": "string"}, "table": {"type": "string"}}, ["workspace_id", "dataset", "table"]), any_object, {"destructiveHint": False}),
        FoundationMcpTool("get_registration_status", "1", "Get dataset registration status.", _object_schema({"workspace_id": {"type": "string"}, "registration_id": {"type": "string"}}, ["workspace_id", "registration_id"]), any_object, {"readOnlyHint": True}),
        FoundationMcpTool("query_wafers", "1", "Query wafer rows.", _object_schema({"workspace_id": {"type": "string"}, "table": {"type": "string"}, "filters": any_object}, ["workspace_id", "table"]), any_object, {"readOnlyHint": True}),
        FoundationMcpTool("run_tdbb", "1", "Request TDBB processing before and after a change date; returns completed run IDs, budgets and maps.", _tdbb_schema(), any_object, {"destructiveHint": False}),
        FoundationMcpTool("compare_tdbb_runs", "1", "Compare completed TDBB runs by ID and return Foundation-computed budget deltas.", _tdbb_compare_schema(), any_object, {"readOnlyHint": True}),
        FoundationMcpTool("get_tdbb_run", "1", "Get TDBB run metadata.", _object_schema({"run_id": {"type": "string"}}, ["run_id"]), any_object, {"readOnlyHint": True}),
        FoundationMcpTool("get_tdbb_data", "1", "Get TDBB output rows of one run.", _object_schema({"run_id": {"type": "string"}, "tables": {"type": "array", "items": {"type": "string", "enum": ["ce_wafer", "ce_field", "nce_wafer", "nce_field"]}}}, ["run_id"]), any_object, {"readOnlyHint": True}),
    )
