# Analytics Foundation MCP tool provider

This package exposes Analytics Foundation operations as MCP tool metadata and
invocation handlers. Every invocation delegates to the shared
`analytics-foundation-client` HTTP client. It does not import the mock
Foundation service or access datasets directly.

A bridge converts tool metadata into the existing `McpToolDescriptor` model so
that the current generic registry remains authoritative.
