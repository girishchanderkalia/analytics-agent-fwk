"""Errors shared by the LangGraph-centered runtime."""


class LangGraphRuntimeError(RuntimeError):
    """Base error raised by the LangGraph runtime layer."""


class LangGraphDependencyError(LangGraphRuntimeError):
    """Raised when a required runtime dependency is unavailable."""


class StateValidationError(LangGraphRuntimeError, ValueError):
    """Raised when framework-owned graph-state fields are invalid."""
