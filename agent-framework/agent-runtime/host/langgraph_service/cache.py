"""Thread-safe compiled-agent cache keyed by immutable agent identity."""
from __future__ import annotations
from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable

@dataclass(frozen=True)
class CompiledAgentCacheKey:
    agent_id: str
    version: str
    definition_digest: str

class CompiledAgentCache:
    def __init__(self) -> None:
        self._values: dict[CompiledAgentCacheKey, Any] = {}
        self._lock = RLock()

    def get_or_create(self, key: CompiledAgentCacheKey, factory: Callable[[], Any]) -> Any:
        with self._lock:
            if key not in self._values:
                self._values[key] = factory()
            return self._values[key]

    def invalidate(self, *, agent_id: str | None = None, version: str | None = None) -> int:
        with self._lock:
            keys = [
                key for key in self._values
                if (agent_id is None or key.agent_id == agent_id)
                and (version is None or key.version == version)
            ]
            for key in keys: del self._values[key]
            return len(keys)

    def size(self) -> int:
        with self._lock: return len(self._values)
