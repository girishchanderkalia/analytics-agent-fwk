from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent-framework" / "agent-runtime"))

from runtime_service_langgraph.lifecycle import RuntimeServiceLifecycle


class Provider:
    def __init__(self):
        self.ready = False
        self.value = object()
    async def start(self):
        self.ready = True
        return self.value
    async def close(self):
        self.ready = False


def test_lifecycle_starts_checkpointer_before_runtime() -> None:
    provider = Provider()
    events = []
    lifecycle = RuntimeServiceLifecycle(
        provider,
        runtime_factory=lambda checkpointer: events.append(
            ("runtime", checkpointer)
        ) or {"checkpointer": checkpointer},
        service_factory=lambda runtime: events.append(
            ("service", runtime)
        ) or {"runtime": runtime},
    )
    service = asyncio.run(lifecycle.start())
    assert events[0] == ("runtime", provider.value)
    assert lifecycle.ready
    assert service is lifecycle.service
    asyncio.run(lifecycle.close())
    assert not lifecycle.ready
