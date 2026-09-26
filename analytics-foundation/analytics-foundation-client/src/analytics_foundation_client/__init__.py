"""Shared Analytics Foundation HTTP client."""

from .client import AnalyticsFoundationClient
from .errors import (
    FoundationClientError,
    FoundationConnectionError,
    FoundationHttpError,
    FoundationResponseError,
)
from .models import (
    BellCurveRange,
    DatasetMetadata,
    DistributionStats,
    HealthResponse,
    RegistrationRequest,
    RegistrationStatus,
    TrendPoint,
    TrendQueryRequest,
    TrendResponse,
    TrendSeries,
    WaferQueryRequest,
    WaferQueryResponse,
    WorkspaceConnectionInfo,
    WorkspaceFiltersRequest,
    WorkspaceFiltersResponse,
    WorkspaceResponse,
)
from .settings import AnalyticsFoundationClientSettings

__all__ = [
    "AnalyticsFoundationClient",
    "AnalyticsFoundationClientSettings",
    "BellCurveRange",
    "DatasetMetadata",
    "DistributionStats",
    "FoundationClientError",
    "FoundationConnectionError",
    "FoundationHttpError",
    "FoundationResponseError",
    "HealthResponse",
    "RegistrationRequest",
    "RegistrationStatus",
    "TrendPoint",
    "TrendQueryRequest",
    "TrendResponse",
    "TrendSeries",
    "WaferQueryRequest",
    "WaferQueryResponse",
    "WorkspaceConnectionInfo",
    "WorkspaceFiltersRequest",
    "WorkspaceFiltersResponse",
    "WorkspaceResponse",
]
