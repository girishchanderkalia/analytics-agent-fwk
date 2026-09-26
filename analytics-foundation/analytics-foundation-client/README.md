# Shared Analytics Foundation HTTP client

This package is the Python HTTP boundary for the Slice 13A Analytics Foundation
API. It is intended for MCP tools and other Python consumers.

Properties:

- Async `httpx` transport.
- Pydantic request and response validation.
- Contract-specific methods only.
- Typed connection, HTTP, and response-validation errors.
- Injectable `httpx.AsyncClient` for tests and deployment-specific transport.
- Configurable TLS verification without disabling verification by default.

The client does not import the mock Foundation service implementation and does
not contain OPO workflow logic.
