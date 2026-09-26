"""Compose the LangGraph-backed Runtime Service."""
from host.langgraph_service import AgentVersionResolver, LangGraphRuntimeService
from host.langgraph_service.sqlite_metadata_store import SQLiteConversationMetadataStore

def create_langgraph_runtime_service(*, agent_repository, compiler, dependency_factory, checkpointer, metadata_database_path):
    return LangGraphRuntimeService(
        resolver=AgentVersionResolver(agent_repository),
        compiler=compiler,
        dependency_factory=dependency_factory,
        checkpointer=checkpointer,
        metadata_store=SQLiteConversationMetadataStore(metadata_database_path),
    )
