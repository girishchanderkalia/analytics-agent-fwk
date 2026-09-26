"""FastAPI dependency providers for persisted runtime services."""

from __future__ import annotations

from typing import Any

from fastapi import Request


class RuntimeServiceUnavailableError(RuntimeError):
    """Raised when no persisted Runtime Service is configured."""


def get_runtime_service(request: Request) -> Any:
    """Resolve the configured Runtime Service from application state."""

    service = getattr(request.app.state, "runtime_service", None)

    if service is None:
        raise RuntimeServiceUnavailableError(
            "The persisted Application Agent Runtime service is not configured"
        )

    return service
