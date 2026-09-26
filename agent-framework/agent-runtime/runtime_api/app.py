"""FastAPI application factory for the persisted Runtime Service."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .error_mapping import install_error_handlers
from .readiness import router as readiness_router
from .routes import router


def create_app(runtime_service: Any | None = None) -> FastAPI:
    """Create the Runtime API and inject the persisted Runtime Service."""

    app = FastAPI(
        title="Application Agent Runtime API",
        version="2.1.0",
        description=(
            "Start, resume, and inspect durable application-agent conversations."
        ),
    )

    app.state.runtime_service = runtime_service
    install_error_handlers(app)
    app.include_router(router)
    app.include_router(readiness_router)
    return app
