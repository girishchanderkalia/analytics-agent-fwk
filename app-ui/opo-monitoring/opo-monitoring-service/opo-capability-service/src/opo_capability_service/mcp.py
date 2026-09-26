from __future__ import annotations
from typing import Any
from .catalog import TOOLS, TOOL_BY_NAME
from .errors import CapabilityInputError, UnknownCapabilityError
from .service import OpoCapabilityService

class McpHandler:
    def __init__(self, service: OpoCapabilityService | None = None) -> None:
        self.service=service or OpoCapabilityService()

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        identifier=request.get("id")
        method=request.get("method")
        try:
            if method == "initialize":
                result={"protocolVersion":"2025-06-18","capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"opo-capability-service","version":"0.1.0"}}
            elif method == "tools/list":
                result={"tools":[{"name":t.name,"title":t.title,"description":t.description,"inputSchema":t.input_schema} for t in TOOLS]}
            elif method == "tools/call":
                params=request.get("params") or {}
                name=params.get("name")
                if name not in TOOL_BY_NAME: raise UnknownCapabilityError(str(name))
                output=self.service.invoke(name, params.get("arguments") or {})
                result={"content":[{"type":"text","text":"OPO capability completed"}],"structuredContent":output,"isError":False}
            else:
                return self._error(identifier,-32601,"Method not found")
            return {"jsonrpc":"2.0","id":identifier,"result":result}
        except UnknownCapabilityError as exc:
            return self._error(identifier,-32602,f"Unknown tool: {exc}")
        except CapabilityInputError as exc:
            return self._error(identifier,-32602,f"Invalid tool arguments: {exc}")
        except Exception:
            return self._error(identifier,-32603,"Internal error")

    @staticmethod
    def _error(identifier: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc":"2.0","id":identifier,"error":{"code":code,"message":message}}
