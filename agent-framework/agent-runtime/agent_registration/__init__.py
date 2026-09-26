"""Bulk registration of prebuilt application agents."""

from .catalog import InMemoryAgentRegistrationCatalog
from .errors import (
    AgentAlreadyRegisteredError,
    AgentRegistrationError,
    AgentRegistrationValidationError,
)
from .models import (
    AgentRegistrationKey,
    AgentRegistrationRecord,
    AgentRegistrationRequest,
    BulkAgentRegistrationRequest,
    BulkAgentRegistrationResult,
    RegistrationStatus,
)
from .package_validator import GenericAgentPackageRegistrationValidator, fingerprint_agent_package
from .service import AgentRegistrationService, AgentRegistrationValidator

__all__ = [
    "AgentAlreadyRegisteredError",
    "AgentRegistrationError",
    "AgentRegistrationKey",
    "AgentRegistrationRecord",
    "AgentRegistrationRequest",
    "AgentRegistrationService",
    "AgentRegistrationValidationError",
    "AgentRegistrationValidator",
    "BulkAgentRegistrationRequest",
    "BulkAgentRegistrationResult",
    "GenericAgentPackageRegistrationValidator",
    "InMemoryAgentRegistrationCatalog",
    "RegistrationStatus",
    "fingerprint_agent_package",
]
