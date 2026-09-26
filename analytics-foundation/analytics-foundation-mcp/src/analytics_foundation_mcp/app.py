from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, Mapping

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from analytics_foundation_client import (
    AnalyticsFoundationClient,
    AnalyticsFoundationClientSettings,
    FoundationClientError,
)

from .errors import FoundationMcpToolNotFoundError
from .provider import AnalyticsFoundationMcpToolProvider


@lru_cache(maxsize=1)
def _client() -> AnalyticsFoundationClient:
    return AnalyticsFoundationClient(
        AnalyticsFoundationClientSettings(
            base_url=os.getenv(
                "ANALYTICS_FOUNDATION_BASE_URL",
                "http://127.0.0.1:8200",
            ),
            connect_timeout_seconds=float(
                os.getenv("ANALYTICS_FOUNDATION_CONNECT_TIMEOUT_SECONDS", "5")
            ),
            read_timeout_seconds=float(
                os.getenv("ANALYTICS_FOUNDATION_READ_TIMEOUT_SECONDS", "60")
            ),
        )
    )


@lru_cache(maxsize=1)
def _provider() -> AnalyticsFoundationMcpToolProvider:
    return AnalyticsFoundationMcpToolProvider(_client())


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    if _client.cache_info().currsize:
        await _client().close()
    _provider.cache_clear()
    _client.cache_clear()


app = FastAPI(
    title="Analytics Foundation MCP",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    await _client().ready()
    return {"status": "ok"}


@app.post("/mcp")
async def mcp(request: Mapping[str, Any]) -> JSONResponse:
    identifier = request.get("id")
    if request.get("jsonrpc") != "2.0":
        return _error(identifier, -32600, "Invalid JSON-RPC request")
    method = request.get("method")
    try:
        if method == "tools/list":
            tools = await _provider().discover_tools()
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": identifier,
                "result": {"tools": [_tool_payload(tool) for tool in tools]},
            })
        if method == "tools/call":
            params = request.get("params") or {}
            if not isinstance(params, Mapping):
                return _error(identifier, -32602, "params must be an object")
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not isinstance(name, str) or not name.strip():
                return _error(identifier, -32602, "tool name is required")
            if not isinstance(arguments, Mapping):
                return _error(identifier, -32602, "tool arguments must be an object")
            result = await _provider().call_tool(name, arguments)
            structured = dict(result.structured_content)
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": identifier,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(structured, separators=(",", ":")),
                    }],
                    "structuredContent": structured,
                    "isError": result.is_error,
                },
            })
        return _error(identifier, -32601, "Method not found")
    except FoundationMcpToolNotFoundError as error:
        return _error(identifier, -32602, str(error))
    except (ValidationError, ValueError, TypeError) as error:
        return _error(identifier, -32602, str(error))
    except FoundationClientError as error:
        return _error(identifier, -32000, str(error))


def _tool_payload(tool: Any) -> dict[str, Any]:
    payload = {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": dict(tool.input_schema),
        "outputSchema": dict(tool.output_schema),
    }
    if tool.annotations:
        payload["annotations"] = dict(tool.annotations)
    return payload


def _error(identifier: Any, code: int, message: str) -> JSONResponse:
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": identifier,
        "error": {"code": code, "message": message},
    })
