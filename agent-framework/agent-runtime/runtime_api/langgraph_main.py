"""ASGI entry point serving the persisted chat API from LangGraph."""

from bootstrap.langgraph_runtime_composition import (
    create_langgraph_conversation_service,
)

from .app import create_app

app = create_app(runtime_service=create_langgraph_conversation_service())
