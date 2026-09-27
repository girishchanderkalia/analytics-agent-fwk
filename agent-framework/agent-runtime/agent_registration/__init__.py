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
from .markdown_validator import (
    MarkdownAgentPackageRegistrationValidator,
    fingerprint_markdown_package,
)
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
    "InMemoryAgentRegistrationCatalog",
    "MarkdownAgentPackageRegistrationValidator",
    "RegistrationStatus",
    "fingerprint_markdown_package",
]
