"""Generic MCP registry with temporary governed-invocation compatibility."""

from .client import MCPClient, MCPDiscoveredTool, MCPToolResult
from .discovery import McpToolDiscoveryService
from .errors import (
    DuplicateMcpToolError,
    InvalidMcpToolError,
    MCPRegistrationError,
    MCPServerNotFoundError,
    MCPToolApprovalRequiredError,
    MCPToolAuthorizationError,
    MCPToolError,
    MCPToolInvocationError,
    MCPToolNotFoundError,
    MCPToolSchemaError,
    McpToolAllowlistError,
    McpToolNotFoundError,
    McpToolRegistryError,
)
from .models import (
    AgentToolReference,
    MCPApprovalMode,
    MCPServerRegistration,
    MCPToolRegistration,
    MCPToolSecurityContext,
    McpToolDescriptor,
    McpToolKey,
)
from .protocols import McpToolDiscoveryClient
from .registry import McpToolRegistry

__all__ = [
    "AgentToolReference",
    "DuplicateMcpToolError",
    "InvalidMcpToolError",
    "MCPApprovalMode",
    "MCPClient",
    "MCPDiscoveredTool",
    "MCPRegistrationError",
    "MCPServerNotFoundError",
    "MCPToolApprovalRequiredError",
    "MCPToolAuthorizationError",
    "MCPToolError",
    "MCPToolInvocationError",
    "MCPToolNotFoundError",
    "MCPToolRegistration",
    "MCPToolResult",
    "MCPToolSchemaError",
    "MCPToolSecurityContext",
    "MCPServerRegistration",
    "McpToolAllowlistError",
    "McpToolDescriptor",
    "McpToolDiscoveryClient",
    "McpToolDiscoveryService",
    "McpToolKey",
    "McpToolNotFoundError",
    "McpToolRegistry",
    "McpToolRegistryError",
]
