"""Generic MCP registry with temporary governed-invocation compatibility."""

from .client import MCPClient, MCPDiscoveredTool, MCPToolResult
from .discovery import McpToolDiscoveryService
from .http_client import HttpMcpClient
from .operation_dispatch import (
    McpOperationDispatchError,
    McpOperationRegistry,
    load_operation_declarations,
)
from .server_registry import (
    environment_variable_for,
    registrations_from_environment,
)
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
from .fixed_registry import create_fixed_tool_registry, fixed_server_ids
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
    "HttpMcpClient",
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
    "McpOperationDispatchError",
    "McpOperationRegistry",
    "environment_variable_for",
    "create_fixed_tool_registry",
    "fixed_server_ids",
    "load_operation_declarations",
    "registrations_from_environment",
]
