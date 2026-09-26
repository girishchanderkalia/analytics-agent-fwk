from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from analytics_foundation_mcp import app as app_module


@dataclass(frozen=True)
class Tool:
    name: str = "query_trends"
    description: str = "Query trends"
    input_schema: dict = None
    output_schema: dict = None
    annotations: dict = None

    def __post_init__(self):
        object.__setattr__(self, "input_schema", {"type": "object"})
        object.__setattr__(self, "output_schema", {"type": "object"})
        object.__setattr__(self, "annotations", {"readOnlyHint": True})


@dataclass(frozen=True)
class Result:
    structured_content: dict
    is_error: bool = False


class Provider:
    async def discover_tools(self):
        return (Tool(),)

    async def call_tool(self, name, arguments):
        return Result({"name": name, "arguments": dict(arguments)})


def test_tools_list_and_call(monkeypatch):
    monkeypatch.setattr(app_module, "_provider", lambda: Provider())
    client = TestClient(app_module.app)
    listed = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": "list", "method": "tools/list", "params": {},
    }).json()
    assert listed["result"]["tools"][0]["name"] == "query_trends"
    called = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": "call", "method": "tools/call",
        "params": {"name": "query_trends", "arguments": {"days": 7}},
    }).json()
    assert called["result"]["structuredContent"] == {
        "name": "query_trends", "arguments": {"days": 7},
    }


def test_health():
    client = TestClient(app_module.app)
    assert client.get("/health").json() == {"status": "ok"}
