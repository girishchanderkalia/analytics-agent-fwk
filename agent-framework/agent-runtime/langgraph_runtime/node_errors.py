"""Errors raised by the standard LangGraph node library."""


class StandardNodeError(RuntimeError):
    """Base error raised while creating or executing a standard node."""


class UnsupportedNodeKindError(StandardNodeError, ValueError):
    """Raised when a normalized node uses an unknown standard kind."""


class NodeConfigurationError(StandardNodeError, ValueError):
    """Raised when a standard node configuration is incomplete or invalid."""


class NodeExecutionError(StandardNodeError):
    """Raised when a standard node dependency fails."""
