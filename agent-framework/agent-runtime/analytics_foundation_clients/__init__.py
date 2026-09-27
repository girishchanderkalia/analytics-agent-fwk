"""Analytics Foundation client contracts and implementations."""

from .http_client import HttpAnalyticsFoundationClient
from .in_memory_client import (
    AnalyticsFoundationClientError,
    AnalyticsFoundationInvalidResultError,
    AnalyticsFoundationOperationNotFoundError,
    InMemoryAnalyticsFoundationClient,
)
from .protocols import (
    AnalyticsFoundationClient,
    AnalyticsFoundationRequest,
    AnalyticsFoundationResponse,
)

__all__ = [
    "AnalyticsFoundationClient",
    "AnalyticsFoundationClientError",
    "AnalyticsFoundationInvalidResultError",
    "AnalyticsFoundationOperationNotFoundError",
    "AnalyticsFoundationRequest",
    "AnalyticsFoundationResponse",
    "HttpAnalyticsFoundationClient",
    "InMemoryAnalyticsFoundationClient",
]