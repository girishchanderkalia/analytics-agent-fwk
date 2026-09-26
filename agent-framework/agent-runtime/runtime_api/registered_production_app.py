"""Build the persisted FastAPI application from fixed registrations."""

from __future__ import annotations

from pathlib import Path

from host.application_registrations import ApplicationRegistrations
from host.production_composition import create_production_runtime_service
from .app import create_app
from .settings import RuntimeSettings


def create_registered_production_app(
    registrations: ApplicationRegistrations,
    settings: RuntimeSettings | None = None,
):
    """Create the runnable persisted API for one application deployment."""

    effective_settings = settings or RuntimeSettings()

    runtime_service = create_production_runtime_service(
        repository_root=Path(__file__).resolve().parents[2],
        database_path=effective_settings.resolved_database_path(),
        capability_registry=registrations.capability_registry,
        operations=registrations.operations,
        permissions=registrations.security_context.permissions,
        approved_capabilities=(
            registrations.security_context.approved_capabilities
        ),
    )

    return create_app(runtime_service=runtime_service)
