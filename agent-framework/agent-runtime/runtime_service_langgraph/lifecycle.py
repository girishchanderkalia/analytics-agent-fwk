"""Production lifecycle composition for Runtime Service and checkpointer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class RuntimeServiceLifecycle:
    """Start persistence before building a runtime that consumes it."""

    checkpointer_provider: Any
    runtime_factory: Callable[[Any], Any]
    service_factory: Callable[[Any], Any]
    runtime: Any = None
    service: Any = None

    async def start(self) -> Any:
        if self.service is not None:
            return self.service
        checkpointer = await self.checkpointer_provider.start()
        self.runtime = self.runtime_factory(checkpointer)
        self.service = self.service_factory(self.runtime)
        return self.service

    async def close(self) -> None:
        self.service = None
        self.runtime = None
        await self.checkpointer_provider.close()

    @property
    def ready(self) -> bool:
        return (
            self.service is not None
            and bool(self.checkpointer_provider.ready)
        )
