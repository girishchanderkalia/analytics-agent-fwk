"""Errors raised by the LangGraph-backed Runtime Service."""

class LangGraphRuntimeServiceError(RuntimeError):
    """Base service error."""

class AgentVersionResolutionError(LangGraphRuntimeServiceError):
    """Raised when an agent or requested version cannot be resolved."""

class ConversationTransitionError(LangGraphRuntimeServiceError):
    """Raised when a conversation cannot start or resume safely."""

class CompiledAgentCacheError(LangGraphRuntimeServiceError):
    """Raised when compiled-agent caching fails."""
