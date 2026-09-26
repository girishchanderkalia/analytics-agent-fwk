"""Runtime Service errors independent of HTTP transport."""


class RuntimeServiceError(RuntimeError):
    """Base migrated Runtime Service error."""


class RuntimeServiceValidationError(RuntimeServiceError, ValueError):
    """Raised when a service request is invalid."""


class RuntimeServiceExecutionError(RuntimeServiceError):
    """Raised when central LangGraph execution fails."""
