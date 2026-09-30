"""Compose the LangGraph-backed runtime from registered markdown packages.

Deployment configuration supplies the application identity, package roots, MCP
endpoints, and persistence; everything else is derived from the packages.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from definitions import translate_markdown_agent
from host.langgraph_conversation_service import LangGraphConversationService
from host.langgraph_service.sqlite_metadata_store import (
    SQLiteConversationMetadataStore,
)
from langgraph_runtime.graph_cache import CompiledGraphCache
from langgraph_runtime.runtime_api import LangGraphAgentRuntime
from mcp_tools import (
    HttpMcpClient,
    create_fixed_tool_registry,
    fixed_server_ids,
    registrations_from_environment,
)
from runtime_service_langgraph import LangGraphRuntimeService

from .langgraph_checkpointer_bootstrap import create_langgraph_checkpointer
from .langgraph_dependencies import McpToolInvoker, NormalizedAgentCompiler
from .markdown_agent_registration import (
    register_application_packages_from_environment,
    register_markdown_agents_from_environment,
)
from .model_gateway_adapter import create_async_model_gateway

APPLICATION_VARIABLE = "AGENT_APPLICATION_ID"
DATABASE_VARIABLE = "AGENT_RUNTIME_DATABASE_PATH"
DEFAULT_DATABASE = "./runtime-data/conversations.sqlite"


def create_langgraph_conversation_service(
    environment: Mapping[str, str] | None = None,
    *,
    model_provider: Any | None = None,
    mcp_client: Any | None = None,
) -> LangGraphConversationService:
    """Build the conversation service backing the persisted chat API."""

    env = dict(os.environ if environment is None else environment)
    application_id = env.get(APPLICATION_VARIABLE, "").strip()
    if not application_id:
        raise ValueError(
            f"Required environment variable is missing: {APPLICATION_VARIABLE}"
        )

    catalog, _ = register_markdown_agents_from_environment(
        application_id=application_id,
        environment=env,
    )
    register_application_packages_from_environment(environment=env, catalog=catalog)

    client = mcp_client or HttpMcpClient()
    servers = registrations_from_environment(fixed_server_ids(), env)

    runtime = LangGraphAgentRuntime(
        registration_catalog=catalog,
        normalizer=translate_markdown_agent,
        compiler=NormalizedAgentCompiler(
            model_provider=model_provider or create_async_model_gateway(),
            tool_registry=create_fixed_tool_registry(),
            tool_invoker=McpToolInvoker(client, servers),
        ),
        graph_cache=CompiledGraphCache(),
        checkpointer=create_langgraph_checkpointer(env).checkpointer,
    )

    return LangGraphConversationService(
        runtime_service=LangGraphRuntimeService(runtime),
        catalog=catalog,
        metadata_store=SQLiteConversationMetadataStore(_database_path(env)),
        normalizer=translate_markdown_agent,
    )


def _database_path(environment: Mapping[str, str]) -> Path:
    configured = environment.get(DATABASE_VARIABLE, DEFAULT_DATABASE).strip()
    path = Path(configured or DEFAULT_DATABASE).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
