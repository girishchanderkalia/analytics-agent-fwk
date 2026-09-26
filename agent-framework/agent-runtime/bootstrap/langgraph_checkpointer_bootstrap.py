"""Production bootstrap for the configured LangGraph checkpointer."""
from __future__ import annotations
import os
from langgraph_runtime.checkpointing import (
    CheckpointerBackend, CheckpointerFactory, CheckpointerHandle,
    CheckpointerSettings,
)

def create_langgraph_checkpointer(
    environment: dict[str,str] | None = None,
) -> CheckpointerHandle:
    env=dict(os.environ if environment is None else environment)
    raw=env.get("AGENT_RUNTIME_CHECKPOINTER_BACKEND","memory").strip().lower()
    try:
        backend=CheckpointerBackend(raw)
    except ValueError as exc:
        raise ValueError(f"Unsupported AGENT_RUNTIME_CHECKPOINTER_BACKEND: {raw}") from exc
    settings=CheckpointerSettings(
        backend=backend,
        connection_string=env.get("AGENT_RUNTIME_CHECKPOINTER_CONNECTION_STRING"),
        setup_schema=env.get("AGENT_RUNTIME_CHECKPOINTER_SETUP","false").lower() in {"1","true","yes"},
    )
    return CheckpointerFactory().create(settings)
