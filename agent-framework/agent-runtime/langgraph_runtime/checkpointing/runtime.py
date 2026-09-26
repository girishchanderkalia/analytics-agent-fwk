"""Checkpoint-aware graph invocation facade."""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from .identity import CheckpointIdentity

class CheckpointRuntime:
    def __init__(self, graph: Any) -> None:
        self.graph=graph

    def start(self, *, conversation_id: str, state: Mapping[str, Any]) -> Any:
        return self.graph.invoke(
            dict(state),
            config=CheckpointIdentity(conversation_id).configurable(),
        )

    def resume(self, *, conversation_id: str, command: Any) -> Any:
        return self.graph.invoke(
            command,
            config=CheckpointIdentity(conversation_id).configurable(),
        )

    def get_state(self, *, conversation_id: str) -> Any:
        return self.graph.get_state(
            CheckpointIdentity(conversation_id).configurable()
        )
