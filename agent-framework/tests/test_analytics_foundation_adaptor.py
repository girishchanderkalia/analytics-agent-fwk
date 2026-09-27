"""Tests for the Analytics Foundation Capability Adaptor."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest


V3_ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"
OPO_AGENT_ROOT = (
    V3_ROOT
    / "agents"
    / "opo-monitoring"
)

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(AGENT_RUNTIME_ROOT),
    )


from analytics_foundation_clients import (  # noqa: E402
    InMemoryAnalyticsFoundationClient,
)
from capabilities import (  # noqa: E402
    AnalyticsFoundationAdaptor,
    AnalyticsFoundationAdaptorError,
    CapabilityApprovalError,
    CapabilityContext,
    CapabilityPermissionError,
)
from execution.definition_loader import (  # noqa: E402
    load_agent_definition,
)


@pytest.fixture
def adaptor() -> AnalyticsFoundationAdaptor:
    bundle = load_agent_definition(
        OPO_AGENT_ROOT
    )

    client = InMemoryAnalyticsFoundationClient()

    client.register(
        "read_trends",
        lambda request: {
            "series": [
                {
                    "days": request["days"],
                    "value": 10,
                }
            ]
        },
    )

    client.register(
        "read_distribution_stats",
        lambda request: {
            "sample_count": 1,
            "p95": 9.5,
            "p99": 10.0,
        },
    )

    client.register(
        "create_workspace",
        lambda request: {
            "workspace_id": "workspace-1",
        },
    )

    client.register(
        "add_filters",
        lambda request: {
            "workspace_id": request["workspace_id"],
            "filters": request["filters"],
        },
    )

    client.register(
        "register_dataset",
        lambda request: {
            "status": "registered",
            "workspace_id": request["workspace_id"],
        },
    )

    client.register(
        "read_wafers",
        lambda request: {
            "rows": [
                {
                    "waferId": "wafer-1",
                }
            ]
        },
    )

    created = AnalyticsFoundationAdaptor(
        bundle,
        client,
    )

    created.register_declared_capabilities()

    return created


def test_registers_all_declared_capabilities(
    adaptor: AnalyticsFoundationAdaptor,
) -> None:
    assert adaptor.registry.names() == [
        "data_query.read_distribution_stats",
        "data_query.read_trends",
        "data_query.read_wafers",
        "workspace.add_filters",
        "workspace.create",
        "workspace.register_dataset",
    ]


def test_invokes_trend_capability(
    adaptor: AnalyticsFoundationAdaptor,
) -> None:
    context = CapabilityContext.create(
        permissions={
            "query:trends:read",
        },
    )

    updates = adaptor.invoke(
        "data_query.read_trends",
        {
            "trend_filters": {
                "lookback_days": 7,
                "start_date": None,
                "end_date": None,
                "lot_ids": [],
                "product_ids": [],
                "layer_ids": [],
                "exposure_equipment_ids": [],
            }
        },
        context=context,
    )

    assert updates == {
        "trend_series": [
            {
                "days": 7,
                "value": 10,
            }
        ]
    }


def test_missing_permission_is_rejected(
    adaptor: AnalyticsFoundationAdaptor,
) -> None:
    with pytest.raises(
        CapabilityPermissionError,
    ):
        adaptor.invoke(
            "data_query.read_trends",
            {
                "trend_filters": {
                    "lookback_days": None,
                    "start_date": None,
                    "end_date": None,
                    "lot_ids": [],
                    "product_ids": [],
                    "layer_ids": [],
                    "exposure_equipment_ids": [],
                },
            },
        )


def test_workspace_creation_maps_result(
    adaptor: AnalyticsFoundationAdaptor,
) -> None:
    context = CapabilityContext.create(
        permissions={
            "workspace:create",
        },
    )

    updates = adaptor.invoke(
        "workspace.create",
        {},
        context=context,
    )

    assert updates == {
        "workspace": {
            "workspace_id": "workspace-1",
        }
    }


def test_registration_requires_approval(
    adaptor: AnalyticsFoundationAdaptor,
) -> None:
    context = CapabilityContext.create(
        permissions={
            "workspace:register",
        },
        approved=False,
    )

    with pytest.raises(
        CapabilityApprovalError,
    ):
        adaptor.invoke(
            "workspace.register_dataset",
            {
                "workspace": {
                    "workspace_id": "workspace-1",
                }
            },
            context=context,
        )


def test_registration_runs_after_approval(
    adaptor: AnalyticsFoundationAdaptor,
) -> None:
    context = CapabilityContext.create(
        permissions={
            "workspace:register",
        },
        approved=True,
    )

    updates = adaptor.invoke(
        "workspace.register_dataset",
        {
            "workspace": {
                "workspace_id": "workspace-1",
            }
        },
        context=context,
    )

    assert updates == {
        "registration": {
            "status": "registered",
            "workspace_id": "workspace-1",
        }
    }


def test_undeclared_capability_is_rejected(
    adaptor: AnalyticsFoundationAdaptor,
) -> None:
    with pytest.raises(
        AnalyticsFoundationAdaptorError,
        match="not declared",
    ):
        adaptor.invoke(
            "unknown.capability",
            {},
        )