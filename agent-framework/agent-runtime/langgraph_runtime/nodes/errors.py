"""Errors raised by standard LangGraph nodes."""

class StandardNodeError(RuntimeError):
    """Base standard-node error."""

class StandardNodeConfigurationError(StandardNodeError):
    """Raised when a node factory receives an invalid definition."""

class StandardNodeExecutionError(StandardNodeError):
    """Raised when a standard node cannot complete safely."""
