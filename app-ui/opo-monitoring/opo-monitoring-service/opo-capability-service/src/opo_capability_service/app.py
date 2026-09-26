from __future__ import annotations
from fastapi import FastAPI
from .mcp import McpHandler

def create_app(handler: McpHandler | None = None) -> FastAPI:
    app=FastAPI(title="OPO Capability Service",version="0.1.0")
    active=handler or McpHandler()
    @app.get("/health")
    def health(): return {"status":"pass"}
    @app.get("/ready")
    def ready(): return {"status":"ready","tools":3}
    @app.post("/mcp")
    def mcp(request: dict): return active.handle(request)
    return app

app=create_app()
