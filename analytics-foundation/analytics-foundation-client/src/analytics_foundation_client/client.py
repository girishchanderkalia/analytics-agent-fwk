"""Async HTTP client for the Analytics Foundation API."""

from __future__ import annotations

import json
import logging
from time import perf_counter
from collections.abc import Mapping
from typing import Any, TypeVar
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ValidationError

from .errors import (
    FoundationConnectionError,
    FoundationHttpError,
    FoundationResponseError,
)
from .models import (
    DatasetMetadata,
    DistributionStats,
    HealthResponse,
    RegistrationRequest,
    RegistrationStatus,
    TdbbRunData,
    TdbbCompareRequest,
    TdbbCompareResult,
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


logger = logging.getLogger(__name__)
from .settings import AnalyticsFoundationClientSettings

ModelT = TypeVar("ModelT", bound=BaseModel)


class AnalyticsFoundationClient:
    """Reusable async client shared by MCP and Python application consumers."""

    def __init__(
        self,
        settings: AnalyticsFoundationClientSettings,
        *,
        http_client: httpx.AsyncClient | None = None,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        self.settings = settings
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=httpx.Timeout(
                connect=settings.connect_timeout_seconds,
                read=settings.read_timeout_seconds,
                write=settings.read_timeout_seconds,
                pool=settings.connect_timeout_seconds,
            ),
            verify=settings.verify_tls,
            headers=dict(default_headers or {}),
        )

    async def __aenter__(self) -> "AnalyticsFoundationClient":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def health(self) -> HealthResponse:
        return await self._request("GET", "/health", HealthResponse)

    async def ready(self) -> HealthResponse:
        return await self._request("GET", "/ready", HealthResponse)

    async def get_metadata(self) -> DatasetMetadata:
        return await self._request("GET", "/metadata", DatasetMetadata)

    async def get_display_trends(
        self,
        request: TrendQueryRequest | None = None,
    ) -> TrendResponse:
        query = request or TrendQueryRequest()
        params = _query_parameters(query)
        return await self._request(
            "GET",
            "/trends",
            TrendResponse,
            params=params,
        )

    async def query_trends(self, request: TrendQueryRequest) -> TrendResponse:
        return await self._request(
            "POST",
            "/trends/query",
            TrendResponse,
            json_body=request.model_dump(mode="json"),
        )

    async def get_distribution(
        self,
        request: TrendQueryRequest,
    ) -> DistributionStats:
        return await self._request(
            "POST",
            "/trends/distribution",
            DistributionStats,
            json_body=request.model_dump(mode="json"),
        )

    async def create_workspace(self) -> WorkspaceResponse:
        return await self._request(
            "POST",
            "/workspaces",
            WorkspaceResponse,
        )

    async def add_workspace_filters(
        self,
        workspace_id: str,
        request: WorkspaceFiltersRequest,
    ) -> WorkspaceFiltersResponse:
        return await self._request(
            "POST",
            f"/workspaces/{_segment(workspace_id)}/filters",
            WorkspaceFiltersResponse,
            json_body=request.model_dump(mode="json"),
        )

    async def get_workspace_connection_info(
        self,
        workspace_id: str,
    ) -> WorkspaceConnectionInfo:
        return await self._request(
            "GET",
            f"/workspaces/{_segment(workspace_id)}/connection-info",
            WorkspaceConnectionInfo,
        )

    async def register_dataset(
        self,
        workspace_id: str,
        request: RegistrationRequest,
    ) -> RegistrationStatus:
        return await self._request(
            "POST",
            f"/workspaces/{_segment(workspace_id)}/registrations",
            RegistrationStatus,
            json_body=request.model_dump(mode="json"),
        )

    async def get_registration_status(
        self,
        workspace_id: str,
        registration_id: str,
    ) -> RegistrationStatus:
        return await self._request(
            "GET",
            f"/workspaces/{_segment(workspace_id)}/registrations/"
            f"{_segment(registration_id)}",
            RegistrationStatus,
        )

    async def query_wafers(
        self,
        request: WaferQueryRequest,
    ) -> WaferQueryResponse:
        return await self._request(
            "POST",
            "/wafers/query",
            WaferQueryResponse,
            json_body=request.model_dump(mode="json"),
        )

    async def run_tdbb(self, request: TdbbRunRequest) -> TdbbRunResult:
        return await self._request(
            "POST",
            "/tdbb/runs",
            TdbbRunResult,
            json_body=request.model_dump(mode="json"),
        )

    async def compare_tdbb_runs(self, request: TdbbCompareRequest) -> TdbbCompareResult:
        return await self._request(
            "POST",
            "/tdbb/compare",
            TdbbCompareResult,
            json_body=request.model_dump(mode="json"),
        )

    async def get_tdbb_run(self, run_id: str) -> TdbbRunInfo:
        return await self._request(
            "GET",
            f"/tdbb/runs/{_segment(run_id)}",
            TdbbRunInfo,
        )

    async def get_tdbb_data(
        self,
        run_id: str,
        tables: list[str] | None = None,
    ) -> TdbbRunData:
        return await self._request(
            "GET",
            f"/tdbb/runs/{_segment(run_id)}/data",
            TdbbRunData,
            params=[("tables", table) for table in tables or []],
        )

    async def _request(
        self,
        method: str,
        path: str,
        response_model: type[ModelT],
        *,
        params: list[tuple[str, str]] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> ModelT:
        started = perf_counter()
        try:
            response = await self._client.request(
                method,
                path,
                params=params,
                json=dict(json_body) if json_body is not None else None,
            )
        except httpx.RequestError as exc:
            logger.exception(
                "foundation_http_failed method=%s path=%s elapsed_ms=%d",
                method,
                path,
                (perf_counter() - started) * 1000,
            )
            raise FoundationConnectionError(
                f"Could not reach Analytics Foundation for {method} {path}"
            ) from exc

        if not response.is_success:
            raise FoundationHttpError(
                status_code=response.status_code,
                method=method,
                path=path,
                response_body=_safe_response_body(response),
            )

        logger.warning(
            "foundation_http_complete method=%s path=%s status=%s elapsed_ms=%d",
            method,
            path,
            response.status_code,
            (perf_counter() - started) * 1000,
        )

        try:
            return response_model.model_validate(response.json())
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise FoundationResponseError(
                f"Invalid Analytics Foundation response for {method} {path}"
            ) from exc


def _segment(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("path identifier must be a non-empty string")
    return quote(value.strip(), safe="")


def _query_parameters(request: TrendQueryRequest) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    scalar_fields = ("days", "start_date", "end_date")
    list_fields = (
        "lot_ids",
        "product_ids",
        "layer_ids",
        "exposure_equipment_ids",
        "chuck_ids",
    )
    for name in scalar_fields:
        value = getattr(request, name)
        if value is not None:
            values.append((name, str(value)))
    for name in list_fields:
        values.extend((name, item) for item in getattr(request, name))
    return values


def _safe_response_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:4096]
