"""Declarative application-agent registration bootstrap."""

from .bootstrap import RegistrationBootstrap, bootstrap_from_environment
from .errors import (
    DuplicateAgentRegistrationError,
    RegistrationBootstrapError,
    RegistrationValidationError,
)
from .loader import AgentPackageLoader
from .models import AgentRegistration, ToolRegistration
from .registry import InMemoryAgentRegistry

__all__ = [
    "AgentPackageLoader",
    "AgentRegistration",
    "DuplicateAgentRegistrationError",
    "InMemoryAgentRegistry",
    "RegistrationBootstrap",
    "RegistrationBootstrapError",
    "RegistrationValidationError",
    "ToolRegistration",
    "bootstrap_from_environment",
]
