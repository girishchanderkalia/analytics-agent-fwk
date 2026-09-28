from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"
if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))


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


def test_invalid_ca_bundle_preserves_existing_ssl_configuration(
    monkeypatch, tmp_path
) -> None:
    from foundation import model_gateway

    inherited_bundle = tmp_path / "inherited-ca.pem"
    inherited_bundle.write_text("test CA", encoding="utf-8")
    monkeypatch.setenv("AGENT_RUNTIME_CA_BUNDLE_PATH", str(tmp_path / "missing.pem"))
    monkeypatch.setenv("SSL_CERT_FILE", str(inherited_bundle))
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(inherited_bundle))

    model_gateway._configure_ssl("azure")

    assert Path(os.environ["SSL_CERT_FILE"]) == inherited_bundle
    assert Path(os.environ["REQUESTS_CA_BUNDLE"]) == inherited_bundle


def test_valid_ca_bundle_is_applied(monkeypatch, tmp_path) -> None:
    from foundation import model_gateway

    ca_bundle = tmp_path / "custom-ca.pem"
    ca_bundle.write_text("test CA", encoding="utf-8")
    monkeypatch.setenv("AGENT_RUNTIME_CA_BUNDLE_PATH", str(ca_bundle))

    model_gateway._configure_ssl("azure")

    assert os.environ["SSL_CERT_FILE"] == str(ca_bundle)
    assert os.environ["REQUESTS_CA_BUNDLE"] == str(ca_bundle)


def test_openai_does_not_apply_azure_ca_bundle(monkeypatch, tmp_path) -> None:
    from foundation import model_gateway

    inherited_bundle = tmp_path / "inherited-ca.pem"
    inherited_bundle.write_text("test CA", encoding="utf-8")
    monkeypatch.setenv("AGENT_RUNTIME_CA_BUNDLE_PATH", str(tmp_path / "missing.pem"))
    monkeypatch.setenv("SSL_CERT_FILE", str(inherited_bundle))
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(inherited_bundle))

    model_gateway._configure_ssl("openai")

    assert os.environ["SSL_CERT_FILE"] == str(inherited_bundle)
    assert os.environ["REQUESTS_CA_BUNDLE"] == str(inherited_bundle)

