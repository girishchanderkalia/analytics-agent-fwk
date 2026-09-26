"""Tests for declarative capability request and result mappings."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(AGENT_RUNTIME_ROOT),
    )


from capabilities.capability_mapping import (  # noqa: E402
    CapabilityMappingError,
    map_request,
    map_result,
    map_value,
    resolve_reference,
)


def test_resolves_top_level_state_reference() -> None:
    state = {
        "trend_filters": {
            "lookback_days": 7,
        }
    }

    assert resolve_reference(
        "${state.trend_filters}",
        state=state,
    ) == {
        "lookback_days": 7,
    }


def test_resolves_nested_state_reference() -> None:
    state = {
        "workspace": {
            "id": "workspace-1",
        }
    }

    assert resolve_reference(
        "${state.workspace.id}",
        state=state,
    ) == "workspace-1"


def test_resolves_result_reference() -> None:
    result = {
        "rows": [
            {
                "value": 42,
            }
        ]
    }

    assert resolve_reference(
        "${result.rows}",
        result=result,
    ) == [
        {
            "value": 42,
        }
    ]


def test_invalid_reference_is_rejected() -> None:
    with pytest.raises(
        CapabilityMappingError,
        match="Invalid capability reference",
    ):
        resolve_reference(
            "state.workspace.id",
            state={},
        )


def test_missing_reference_field_is_rejected() -> None:
    with pytest.raises(
        CapabilityMappingError,
        match="is missing",
    ):
        resolve_reference(
            "${state.workspace.id}",
            state={
                "workspace": {},
            },
        )


def test_maps_nested_request() -> None:
    mapped = map_request(
        {
            "workspace_id": "${state.workspace.id}",
            "filters": "${state.trend_filters}",
            "options": {
                "mode": "strict",
            },
        },
        {
            "workspace": {
                "id": "workspace-1",
            },
            "trend_filters": {
                "lookback_days": 7,
            },
        },
    )

    assert mapped == {
        "workspace_id": "workspace-1",
        "filters": {
            "lookback_days": 7,
        },
        "options": {
            "mode": "strict",
        },
    }


def test_maps_result_to_state_updates() -> None:
    mapped = map_result(
        {
            "trend_series": "${result.rows}",
        },
        {
            "rows": [
                {
                    "value": 10,
                }
            ]
        },
    )

    assert mapped == {
        "trend_series": [
            {
                "value": 10,
            }
        ]
    }


def test_literal_string_is_preserved() -> None:
    assert map_value(
        "overlay",
        state={},
    ) == "overlay"


def test_mapped_value_is_copied() -> None:
    state = {
        "filters": {
            "lot_ids": [
                "LOT-1",
            ]
        }
    }

    mapped = map_request(
        {
            "filters": "${state.filters}",
        },
        state,
    )

    mapped["filters"]["lot_ids"].append(
        "LOT-2"
    )

    assert state == {
        "filters": {
            "lot_ids": [
                "LOT-1",
            ]
        }
    }