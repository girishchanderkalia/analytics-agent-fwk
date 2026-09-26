from __future__ import annotations

from collections.abc import Mapping
from typing import Any

EVIDENCE_FIELDS = (
    "mode",
    "limit_value",
    "requested_limit_value",
    "direction",
    "threshold_unit",
    "baseline_deviation_pct",
    "threshold_context",
    "threshold_recommendation",
    "interpretation",
    "lookback_days",
    "start_date",
    "end_date",
    "lot_ids",
    "product_ids",
    "layer_ids",
    "exposure_equipment_ids",
    "trend_series",
    "analysis",
    "outliers",
    "selected_outlier",
    "workspace_id",
    "filters",
    "registration",
    "registration_history",
    "anomalous_wafers",
    "wafer_rows",
    "selected_action",
    "spatial_pattern",
)


def build_evidence(state: Mapping[str, Any]) -> dict[str, Any]:
    """Project runtime state into the exact legacy evidence field set."""
    wafer_data = _mapping_or_empty(state.get("wafer_data"))
    return {
        "mode": state.get("mode"),
        "limit_value": state.get("limit_value"),
        "requested_limit_value": state.get("requested_limit_value"),
        "direction": state.get("direction"),
        "threshold_unit": state.get("threshold_unit"),
        "baseline_deviation_pct": state.get("baseline_deviation_pct"),
        "threshold_context": state.get("threshold_context"),
        "threshold_recommendation": state.get("threshold_recommendation"),
        "interpretation": state.get("interpretation"),
        "lookback_days": state.get("lookback_days"),
        "start_date": state.get("start_date"),
        "end_date": state.get("end_date"),
        "lot_ids": state.get("lot_ids"),
        "product_ids": state.get("product_ids"),
        "layer_ids": state.get("layer_ids"),
        "exposure_equipment_ids": state.get("exposure_equipment_ids"),
        "trend_series": state.get("trend_series"),
        "analysis": state.get("analysis"),
        "outliers": state.get("outliers"),
        "selected_outlier": state.get("selected"),
        "workspace_id": state.get("workspace_id"),
        "filters": state.get("filters"),
        "registration": state.get("registration"),
        "registration_history": state.get("registration_history"),
        "anomalous_wafers": wafer_data.get("anomalous_wafers"),
        "wafer_rows": wafer_data.get("rows"),
        "selected_action": state.get("selected_action"),
        "spatial_pattern": state.get("spatial_pattern"),
    }


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
