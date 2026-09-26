from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parent / "analytics-foundation-client" / "src"))
sys.path.insert(0, str(ROOT.parent / "agent-runtime"))

from analytics_foundation_client import (
    DatasetMetadata,
    DistributionStats,
    RegistrationStatus,
    TrendResponse,
    WaferQueryResponse,
    WorkspaceConnectionInfo,
    WorkspaceFiltersResponse,
    WorkspaceResponse,
)
from analytics_foundation_mcp import (
    AnalyticsFoundationMcpToolProvider,
    FoundationMcpToolNotFoundError,
)
from analytics_foundation_mcp.registry_bridge import to_registry_descriptors
from mcp_tools import McpToolRegistry


class FakeFoundationClient:
    def __init__(self):
        self.calls = []

    async def query_trends(self, request):
        self.calls.append(("query_trends", request.model_dump()))
        return TrendResponse(series=[])

    async def get_distribution(self, request):
        self.calls.append(("get_distribution", request.model_dump()))
        return DistributionStats(sample_count=0)

    async def get_metadata(self):
        self.calls.append(("get_metadata", {}))
        return DatasetMetadata(trend_table="trend", wafer_table="wafer")

    async def create_workspace(self):
        self.calls.append(("create_workspace", {}))
        return WorkspaceResponse(workspace_id="w-1")

    async def add_workspace_filters(self, workspace_id, request):
        self.calls.append(("add_workspace_filters", workspace_id, request.model_dump()))
        return WorkspaceFiltersResponse(workspace_id=workspace_id, filters=request.filters)

    async def get_workspace_connection_info(self, workspace_id):
        return WorkspaceConnectionInfo(workspace_id=workspace_id, values={})

    async def register_dataset(self, workspace_id, request):
        return RegistrationStatus(registration_id="r-1", workspace_id=workspace_id, status="READY", progress_pct=100, table=request.table)

    async def get_registration_status(self, workspace_id, registration_id):
        return RegistrationStatus(registration_id=registration_id, workspace_id=workspace_id, status="READY", progress_pct=100, table="table")

    async def query_wafers(self, request):
        return WaferQueryResponse(workspace_id=request.workspace_id, table=request.table, rows=[], anomalous_wafers=[])


def run(awaitable):
    return asyncio.run(awaitable)


def test_discovery_registers_with_existing_registry() -> None:
    provider = AnalyticsFoundationMcpToolProvider(FakeFoundationClient())
    tools = run(provider.discover_tools())
    assert len(tools) == 9
    registry = McpToolRegistry()
    registry.register_many(to_registry_descriptors(tools))
    assert len(registry.snapshot()) == 9
    assert all(item.key.server == "analytics-foundation" for item in registry.snapshot())


def test_trend_tools_use_shared_client_models() -> None:
    client = FakeFoundationClient()
    provider = AnalyticsFoundationMcpToolProvider(client)
    result = run(provider.call_tool("query_trends", {"days": 14, "lot_ids": ["L1"]}))
    assert result.structured_content == {"series": []}
    assert client.calls[0][0] == "query_trends"
    stats = run(provider.call_tool("get_distribution_stats", {}))
    assert stats.structured_content["sample_count"] == 0


def test_workspace_tools_delegate_to_shared_client() -> None:
    client = FakeFoundationClient()
    provider = AnalyticsFoundationMcpToolProvider(client)
    created = run(provider.call_tool("create_workspace", {}))
    assert created.structured_content["workspace_id"] == "w-1"
    filtered = run(provider.call_tool("add_workspace_filters", {"workspace_id": "w-1", "filters": {"machine": "M1"}}))
    assert filtered.structured_content["filters"] == {"machine": "M1"}


def test_registration_and_wafer_tools_delegate() -> None:
    provider = AnalyticsFoundationMcpToolProvider(FakeFoundationClient())
    registration = run(provider.call_tool("register_dataset", {"workspace_id": "w-1", "dataset": "overlay", "table": "wafer"}))
    assert registration.structured_content["status"] == "READY"
    status = run(provider.call_tool("get_registration_status", {"workspace_id": "w-1", "registration_id": "r-1"}))
    assert status.structured_content["registration_id"] == "r-1"
    wafers = run(provider.call_tool("query_wafers", {"workspace_id": "w-1", "table": "wafer", "filters": {}}))
    assert wafers.structured_content["rows"] == []


def test_unknown_tool_is_rejected() -> None:
    provider = AnalyticsFoundationMcpToolProvider(FakeFoundationClient())
    with pytest.raises(FoundationMcpToolNotFoundError):
        run(provider.call_tool("missing", {}))


def test_strict_arguments_are_enforced() -> None:
    provider = AnalyticsFoundationMcpToolProvider(FakeFoundationClient())
    with pytest.raises(ValueError):
        run(provider.call_tool("create_workspace", {"unexpected": True}))
    with pytest.raises(ValueError):
        run(provider.call_tool("register_dataset", {"workspace_id": "w-1", "dataset": "d", "table": "t", "unexpected": True}))


def test_no_mock_foundation_implementation_imports() -> None:
    source = (ROOT / "src" / "analytics_foundation_mcp" / "provider.py").read_text(encoding="utf-8")
    assert "foundation_api" not in source
    assert "analytics_foundation_clients" not in source
