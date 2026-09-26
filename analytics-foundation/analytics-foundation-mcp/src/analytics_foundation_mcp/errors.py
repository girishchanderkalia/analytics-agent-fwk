class FoundationMcpToolError(RuntimeError):
    """Base error raised by the Foundation MCP tool provider."""


class FoundationMcpToolNotFoundError(FoundationMcpToolError, LookupError):
    """Raised when an unknown tool is requested."""
