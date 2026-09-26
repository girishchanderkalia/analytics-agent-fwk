"""Readiness endpoint for the configured production runtime."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


router = APIRouter()


@router.get("/ready", tags=["health"])
def readiness(request: Request):
    """Report whether a persisted Runtime Service was injected."""

    service = getattr(request.app.state, "runtime_service", None)

    if service is not None:
        return {"status": "ready"}

    return JSONResponse(
        status_code=503,
        content={
            "status": "not_ready",
            "message": "Runtime Service is not configured",
        },
    )
