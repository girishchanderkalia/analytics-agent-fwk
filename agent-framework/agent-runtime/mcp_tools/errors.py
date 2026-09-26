class McpToolRegistryError(RuntimeError): pass
class InvalidMcpToolError(McpToolRegistryError, ValueError): pass
class DuplicateMcpToolError(McpToolRegistryError): pass
class McpToolNotFoundError(McpToolRegistryError, LookupError): pass
class McpToolAllowlistError(McpToolRegistryError, ValueError): pass
class MCPToolError(RuntimeError): pass
class MCPRegistrationError(MCPToolError): pass
class MCPToolNotFoundError(MCPToolError): pass
class MCPServerNotFoundError(MCPToolError): pass
class MCPToolAuthorizationError(MCPToolError): pass
class MCPToolApprovalRequiredError(MCPToolAuthorizationError): pass
class MCPToolSchemaError(MCPToolError): pass
class MCPToolInvocationError(MCPToolError): pass
