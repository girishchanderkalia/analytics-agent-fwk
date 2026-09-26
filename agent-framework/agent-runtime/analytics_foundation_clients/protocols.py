"""Client contracts used to invoke Analytics Foundation operations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable


AnalyticsFoundationRequest = Mapping[str, Any]
AnalyticsFoundationResponse = dict[str, Any]


@runtime_checkable
class AnalyticsFoundationClient(Protocol):
    """Protocol implemented by Analytics Foundation clients."""

    def invoke(
        self,
        operation: str,
        request: AnalyticsFoundationRequest,
    ) -> AnalyticsFoundationResponse:
        """Invoke one Analytics Foundation operation."""