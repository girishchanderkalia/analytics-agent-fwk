"""Map LangGraph values and interrupts to the existing public contract."""
from __future__ import annotations
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

class LangGraphResultMapper:
    _internal = {
        "thread_id", "threadId", "checkpoint_id", "checkpointId",
        "checkpoint_ns", "current_node", "currentNode", "messages",
        "capability_events", "pending_approval", "pending_action",
    }

    def map(self, value: Any) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
        state = self._state(value)
        interrupt = self._interrupt(value)
        status = "waiting_for_approval" if interrupt is not None else str(state.get("status", "completed"))
        public = {
            key: deepcopy(item)
            for key, item in state.items()
            if key not in self._internal
        }
        return status, public, interrupt

    @staticmethod
    def _state(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping): return dict(value)
        values = getattr(value, "values", None)
        if isinstance(values, Mapping): return dict(values)
        raise TypeError("LangGraph result does not expose state values")

    @staticmethod
    def _interrupt(value: Any) -> dict[str, Any] | None:
        interrupts = getattr(value, "interrupts", None)
        if interrupts is None and isinstance(value, Mapping): interrupts = value.get("__interrupt__")
        if not interrupts: return None
        first = interrupts[0] if isinstance(interrupts, (list, tuple)) else interrupts
        payload = getattr(first, "value", first)
        return dict(payload) if isinstance(payload, Mapping) else {"value": payload}
