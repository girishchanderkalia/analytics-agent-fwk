"""Opaque public conversation identity mapped to LangGraph configuration."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

class CheckpointIdentityError(ValueError):
    pass

@dataclass(frozen=True)
class CheckpointIdentity:
    conversation_id: str
    namespace: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.conversation_id, str) or not self.conversation_id.strip():
            raise CheckpointIdentityError("conversation_id must be a non-empty string")
        if not isinstance(self.namespace, str):
            raise CheckpointIdentityError("namespace must be a string")

    def configurable(self) -> dict[str, Any]:
        values: dict[str, Any] = {"thread_id": self.conversation_id.strip()}
        if self.namespace:
            values["checkpoint_ns"] = self.namespace
        return {"configurable": values}
