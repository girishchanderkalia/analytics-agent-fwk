"""Errors raised by prebuilt application-agent registration."""


class AgentRegistrationError(RuntimeError):
    """Base error raised by the registration subsystem."""


class AgentRegistrationValidationError(AgentRegistrationError, ValueError):
    """Raised when an application submits an invalid agent package."""


class AgentAlreadyRegisteredError(AgentRegistrationError):
    """Raised when an active registration already uses the same key."""
