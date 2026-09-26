class RegistrationBootstrapError(RuntimeError):
    """Base registration-bootstrap failure."""


class RegistrationValidationError(RegistrationBootstrapError, ValueError):
    """Raised when a declarative agent package is invalid."""


class DuplicateAgentRegistrationError(RegistrationBootstrapError):
    """Raised when the same identity has different content."""
