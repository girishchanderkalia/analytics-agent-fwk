# Agent registration bootstrap

Loads declarative application-agent packages, validates cross-file references,
validates MCP tool availability and registers packages idempotently.

The bootstrap is environment driven through `AGENT_PACKAGE_MANIFESTS`, using a
semicolon separator for Windows-compatible execution. It provides an adapter
for the existing MCP tool registry while keeping the agent registry boundary a
small protocol.
