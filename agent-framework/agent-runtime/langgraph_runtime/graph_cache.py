"""Thread-safe in-memory cache for compiled LangGraph graphs."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Any

from .runtime_models import CompiledGraphKey


class CompiledGraphCache:
    """Cache compiled graphs by registration identity and fingerprint."""

    def __init__(self) -> None:
        self._graphs: dict[CompiledGraphKey, Any] = {}
        self._lock = RLock()

    def get(self, key: CompiledGraphKey) -> Any | None:
        with self._lock:
            return self._graphs.get(key)

    def get_or_create(
        self,
        key: CompiledGraphKey,
        factory: Callable[[], Any],
    ) -> Any:
        """Return a cached graph or compile once while holding the cache lock."""

        with self._lock:
            graph = self._graphs.get(key)
            if graph is not None:
                return graph
            graph = factory()
            self._graphs[key] = graph
            return graph

    def invalidate(self, key: CompiledGraphKey) -> None:
        with self._lock:
            self._graphs.pop(key, None)

    def invalidate_agent(
        self,
        application_id: str,
        agent_id: str,
        version: str,
    ) -> int:
        with self._lock:
            matching = [
                key
                for key in self._graphs
                if key.application_id == application_id
                and key.agent_id == agent_id
                and key.version == version
            ]
            for key in matching:
                del self._graphs[key]
            return len(matching)

    def snapshot_keys(self) -> tuple[CompiledGraphKey, ...]:
        with self._lock:
            return tuple(sorted(self._graphs))
