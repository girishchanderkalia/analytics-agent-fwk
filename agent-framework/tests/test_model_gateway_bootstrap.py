from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"
if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))

from bootstrap.model_gateway_adapter import (  # noqa: E402
    ModelGatewayBootstrapError,
    ModelGatewayResponseError,
    PlatformModelGateway,
    create_model_gateway,
)
from host.provider_mapping import (  # noqa: E402
    ModelGatewayResponseError as MappingGatewayError,
)


class FakeTransport:
    def request(self, **kwargs: Any) -> dict[str, Any]:
        return {"structured_output": {"value": 1}}


def test_error_identity_is_shared() -> None:
    assert MappingGatewayError is ModelGatewayResponseError


def test_async_gateway_passes_schema_tools_to_agent(monkeypatch) -> None:
    from bootstrap.model_gateway_adapter import AsyncPlatformModelGateway

    class FakeTool:
        @classmethod
        def from_schema(cls, **kwargs):
            return kwargs

    monkeypatch.setitem(sys.modules, "pydantic_ai", SimpleNamespace(Tool=FakeTool))
    captured = {}

    class FakeAgent:
        async def run(self, input_text):
            captured["input_text"] = input_text
            return SimpleNamespace(output={"mode": "absolute"})

    def agent_factory(**kwargs):
        captured.update(kwargs)
        return FakeAgent()

    async def get_stats(**kwargs):
        return {"p95": 3.2, "filters": kwargs}

    gateway = AsyncPlatformModelGateway(model=object(), agent_factory=agent_factory)
    output = asyncio.run(gateway.invoke_structured(
        system_prompt="Only grounded values", input_text="Find outliers",
        output_contract=dict,
        tools=[{"name": "get_distribution_stats", "description": "Real stats",
                "json_schema": {"type": "object"}, "function": get_stats}],
    ))

    assert output == {"mode": "absolute"}
    assert captured["tools"][0]["name"] == "get_distribution_stats"
    assert captured["tools"][0]["json_schema"] == {"type": "object"}
    assert asyncio.run(captured["tools"][0]["function"](days=7)) == {
        "p95": 3.2, "filters": {"days": 7}
    }

