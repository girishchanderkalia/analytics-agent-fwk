"""Errors raised by the central LangGraph agent runtime."""


class AgentRuntimeError(RuntimeError):
    """Base central runtime error."""


class RegisteredAgentNotFoundError(AgentRuntimeError, LookupError):
    """Raised when an application has not registered the requested agent."""


class RegisteredAgentIdentityError(AgentRuntimeError, ValueError):
    """Raised when package identity no longer matches its registration."""


class GraphCompilationError(AgentRuntimeError):
    """Raised when package normalization or graph compilation fails."""


class GraphInvocationError(AgentRuntimeError):
    """Raised when a compiled graph invocation fails or returns invalid data."""


class GraphStateUnavailableError(AgentRuntimeError):
    """Raised when a graph state snapshot cannot be retrieved."""


class GraphResumeUnavailableError(AgentRuntimeError):
    """Raised when resume is requested without resumable persistence."""


class InvalidResumeRequestError(AgentRuntimeError, ValueError):
    """Raised when a resume request is incomplete or invalid."""
