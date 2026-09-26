# Repository Context

## Purpose and Architecture

This repository contains a multi-application agent framework, the Analytics Foundation data platform, and an OPO Monitoring application that demonstrates their integration.

- Application teams provide/register agent packages and connect their application UI to the framework's chat/conversation API. Agents are declarative: definitions under `agents/` describe workflows, capabilities, and tool allowlists.
- The agent framework runs agent workflows with LangGraph. Its runtime resolves registered agent definitions, invokes and resumes persisted conversations, and exposes HTTP APIs. The current runtime API uses `POST /v1/chat`, `POST /v1/conversations/{conversation_id}/resume`, and conversation lookup routes.
- Analytics Foundation is the data platform. It exposes REST APIs and a shared HTTP client for deterministic data and workspace operations.
- In the OPO Monitoring example, the application backend/BFF has separate downstream clients: deterministic operations call Analytics Foundation REST directly; chat, resume, and conversation lookup call the agent runtime. Treat “UI calls” here as application-facing flows through the BFF unless browser code proves otherwise.
- AI workflows can access Foundation data through governed MCP tools. `analytics-foundation-mcp` publishes tool discovery and invocation over MCP and delegates each operation to `analytics-foundation-client`, which calls Foundation REST. The framework discovers/registers MCP tools and agent definitions constrain which tools an agent may use. MCP, not “MPC,” is the protocol name.

Keep these boundaries clear: deterministic application data access is not agent execution; the app BFF is not the agent runtime; MCP is the tool interface to Foundation for agent workflows, not a separate data store. Do not make UI code import Foundation service implementation or access its backing datasets directly.

## Repository Map

- `agent-framework/agent-runtime/`: runtime APIs, LangGraph execution, agent registration/composition, workflow definitions/loaders, MCP tool registry, persistence, and runtime services.
- `agent-framework/agent-registration-bootstrap/`: loads and validates application-agent packages and their MCP tool references.
- `agents/`: example declarative agent packages, including OPO Monitoring.
- `analytics-foundation/analytics-foundation-api/`: deployable Analytics Foundation REST service.
- `analytics-foundation/analytics-foundation-client/`: reusable typed HTTP client for Foundation APIs.
- `analytics-foundation/analytics-foundation-mcp/`: MCP provider that exposes Foundation operations as tools.
- `app-ui/opo-monitoring/`: example UI and backend facade/BFF, including separate runtime and Foundation clients.
- `agent-framework/integration-tests/`: black-box integration tests across deployed service boundaries; model-backed chat tests may require explicit configuration.
- `deploy/`, `scripts/`, and `docs/`: deployment assets, local slice scripts, and architecture diagrams/status.

## Implementation Guidance

- Follow the existing service boundaries and public HTTP contracts. Use the appropriate runtime client for agent conversations and the Foundation client for deterministic application data needs.
- Keep agent-specific workflow and capability behavior in the agent package and framework/runtime abstractions, rather than embedding it in the UI BFF.
- When changing MCP-backed behavior, preserve tool identity, discovery/registration, schema validation, and the agent's declared allowlist.
- This repository contains compatibility layers and older runtime abstractions alongside the registered LangGraph path. Before changing execution behavior, trace the active composition and API entry point; do not assume similarly named legacy or test-only components are the production path.
- Prefer focused unit tests for a component change and black-box integration tests when changing a cross-service contract.