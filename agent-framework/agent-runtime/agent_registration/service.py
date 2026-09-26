"""Atomic bulk registration service for trusted prebuilt applications."""

from __future__ import annotations

from typing import Protocol

from .catalog import InMemoryAgentRegistrationCatalog
from .models import (
    AgentRegistrationRecord,
    AgentRegistrationRequest,
    BulkAgentRegistrationRequest,
    BulkAgentRegistrationResult,
    RegistrationStatus,
)


class AgentRegistrationValidator(Protocol):
    """Boundary implemented by the later Markdown validation slice."""

    def validate(
        self,
        *,
        application_id: str,
        request: AgentRegistrationRequest,
    ) -> str:
        """Validate a package and return its stable definition fingerprint."""


class AgentRegistrationService:
    """Validate a complete batch before committing any registration."""

    def __init__(
        self,
        catalog: InMemoryAgentRegistrationCatalog,
        validator: AgentRegistrationValidator,
    ) -> None:
        self.catalog = catalog
        self.validator = validator

    def register_bulk(
        self,
        request: BulkAgentRegistrationRequest,
    ) -> BulkAgentRegistrationResult:
        """Atomically register all submitted prebuilt agent packages."""

        staged: list[AgentRegistrationRecord] = []

        for agent in request.agents:
            fingerprint = self.validator.validate(
                application_id=request.application_id,
                request=agent,
            )
            staged.append(
                AgentRegistrationRecord.create(
                    application_id=request.application_id,
                    request=agent,
                    definition_fingerprint=fingerprint,
                )
            )

        registrations = tuple(staged)
        self.catalog.register_atomic(registrations)

        return BulkAgentRegistrationResult(
            application_id=request.application_id,
            status=RegistrationStatus.REGISTERED,
            registrations=registrations,
        )

    def list_for_application(self, application_id: str):
        """List registrations explicitly owned by one application."""
        return self.catalog.list_for_application(application_id)
