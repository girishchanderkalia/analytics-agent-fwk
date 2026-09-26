"""Typed errors raised by the shared Foundation HTTP client."""

from __future__ import annotations

from typing import Any


class FoundationClientError(RuntimeError):
    """Base Analytics Foundation client error."""


class FoundationConnectionError(FoundationClientError):
    """Raised when the Foundation service cannot be reached."""


class FoundationHttpError(FoundationClientError):
    """Raised for non-success HTTP responses."""

    def __init__(
        self,
        *,
        status_code: int,
        method: str,
        path: str,
        response_body: Any = None,
    ) -> None:
        super().__init__(
            f"Analytics Foundation returned HTTP {status_code} for {method} {path}"
        )
        self.status_code = status_code
        self.method = method
        self.path = path
        self.response_body = response_body


class FoundationResponseError(FoundationClientError):
    """Raised when a successful response violates the API contract."""
