"""Synchronous Analytics Foundation client used by governed capabilities.

Operation names match the capability declarations in the agent package; paths
and payloads match the Analytics Foundation OpenAPI contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx

from .in_memory_client import AnalyticsFoundationClientError

TREND_FILTER_FIELDS = (
    "start_date",
    "end_date",
    "lot_ids",
    "product_ids",
    "layer_ids",
    "exposure_equipment_ids",
)

MINIMUM_LOOKBACK_DAYS = 1
MAXIMUM_LOOKBACK_DAYS = 90


class HttpAnalyticsFoundationClient:
    """Invoke Analytics Foundation REST operations over HTTP."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )
        self._operations = {
            "read_trends": self._read_trends,
            "create_workspace": self._create_workspace,
            "add_filters": self._add_filters,
            "register_dataset": self._register_dataset,
            "get_registration": self._get_registration,
            "read_wafers": self._read_wafers,
        }

    def invoke(
        self,
        operation: str,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Invoke one Analytics Foundation operation."""

        if not isinstance(operation, str) or not operation.strip():
            raise AnalyticsFoundationClientError(
                "Analytics Foundation operation must be a non-empty string"
            )
        if not isinstance(request, Mapping):
            raise AnalyticsFoundationClientError(
                "Analytics Foundation request must be a mapping"
            )

        try:
            handler = self._operations[operation.strip()]
        except KeyError as exc:
            raise AnalyticsFoundationClientError(
                f"Analytics Foundation operation is not supported: {operation}"
            ) from exc

        return handler(dict(request))

    def close(self) -> None:
        self._client.close()

    def _read_trends(self, request: dict[str, Any]) -> dict[str, Any]:
        filters = request.get("filters")
        body = _trend_query(filters if isinstance(filters, Mapping) else {})
        response = self._post("/trends/query", body)
        # The capability declares `trend_series: ${result.rows}`.
        return {"rows": response.get("series", [])}

    def _create_workspace(self, _: dict[str, Any]) -> dict[str, Any]:
        return self._post("/workspaces", None)

    def _add_filters(self, request: dict[str, Any]) -> dict[str, Any]:
        workspace_id = _required_text(request, "workspace_id")
        filters = request.get("filters")
        return self._post(
            f"/workspaces/{quote(workspace_id, safe='')}/filters",
            {"filters": dict(filters) if isinstance(filters, Mapping) else {}},
        )

    def _register_dataset(self, request: dict[str, Any]) -> dict[str, Any]:
        workspace_id = _required_text(request, "workspace_id")
        return self._post(
            f"/workspaces/{quote(workspace_id, safe='')}/registrations",
            {
                "dataset": _text(request, "dataset", "overlay"),
                "table": _text(request, "table", "overlay_wafer_points"),
            },
        )

    def _get_registration(self, request: dict[str, Any]) -> dict[str, Any]:
        workspace_id = _required_text(request, "workspace_id")
        registration_id = _required_text(request, "registration_id")
        return self._get(
            f"/workspaces/{quote(workspace_id, safe='')}"
            f"/registrations/{quote(registration_id, safe='')}"
        )

    def _read_wafers(self, request: dict[str, Any]) -> dict[str, Any]:
        workspace_id = _required_text(request, "workspace_id")
        registration = request.get("registration")
        table = _text(
            registration if isinstance(registration, Mapping) else {},
            "table",
            "overlay_wafer_points",
        )
        return self._post(
            "/wafers/query",
            {
                "workspace_id": workspace_id,
                "table": table,
                "filters": _wafer_filters(request.get("selected_outlier")),
            },
        )

    def _post(
        self,
        path: str,
        body: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        return self._send("POST", path, body)

    def _get(self, path: str) -> dict[str, Any]:
        return self._send("GET", path, None)

    def _send(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            response = self._client.request(
                method,
                path,
                json=dict(body) if body is not None else None,
            )
        except httpx.RequestError as exc:
            raise AnalyticsFoundationClientError(
                f"Could not reach Analytics Foundation for {method} {path}"
            ) from exc

        if not response.is_success:
            raise AnalyticsFoundationClientError(
                f"Analytics Foundation returned {response.status_code} "
                f"for {method} {path}: {response.text[:500]}"
            )

        try:
            result = response.json()
        except ValueError as exc:
            raise AnalyticsFoundationClientError(
                f"Analytics Foundation returned invalid JSON for {path}"
            ) from exc

        if not isinstance(result, dict):
            raise AnalyticsFoundationClientError(
                f"Analytics Foundation returned a non-object body for {path}"
            )
        return result


def _trend_query(filters: Mapping[str, Any]) -> dict[str, Any]:
    # No implicit lookback: an unrequested relative window silently hides every
    # row older than it, which reads as "no data" rather than "filtered out".
    body: dict[str, Any] = {}
    for field in TREND_FILTER_FIELDS:
        value = filters.get(field)
        if value in (None, [], ""):
            continue
        body[field] = value

    # The agent contract names this lookback_days; Foundation names it days.
    lookback = filters.get("lookback_days", filters.get("days"))
    if isinstance(lookback, int) and not isinstance(lookback, bool):
        body["days"] = min(
            max(lookback, MINIMUM_LOOKBACK_DAYS),
            MAXIMUM_LOOKBACK_DAYS,
        )
    return body


def _wafer_filters(selected_outlier: Any) -> dict[str, Any]:
    # Wafer rows carry no product column, and narrowing to the single extreme lot
    # would drop the surrounding evidence the investigation needs.
    if not isinstance(selected_outlier, Mapping):
        return {}
    machine = selected_outlier.get("machine")
    if isinstance(machine, str) and machine.strip():
        return {"exposure_equipment_id": machine.strip()}
    return {}


def _required_text(request: Mapping[str, Any], field: str) -> str:
    value = request.get(field)
    if isinstance(value, Mapping):
        value = value.get("workspace_id") if field == "workspace_id" else value
    if not isinstance(value, str) or not value.strip():
        raise AnalyticsFoundationClientError(
            f"Analytics Foundation request requires {field}"
        )
    return value.strip()


def _text(mapping: Mapping[str, Any], field: str, default: str) -> str:
    value = mapping.get(field)
    return value.strip() if isinstance(value, str) and value.strip() else default
