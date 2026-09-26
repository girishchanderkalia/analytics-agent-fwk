from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def normalize_wafer_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one Foundation wafer row without retrieving data."""
    source = dict(row)
    wafer_id = source.get("exposureprocessjob_waferexposureprocessjob_waferid") or source.get("wafer_id") or source.get("waferId") or "UNKNOWN_WAFER"
    lot_id = source.get("exposureprocessjob_lotid") or source.get("lot_id") or source.get("lotId")
    layer_id = source.get("measureprocessjob_layerid") or source.get("layer_id") or source.get("layerId")
    machine = source.get("exposureprocessjob_equipment_equipmentid") or source.get("machine") or source.get("exposureEquipmentId") or "UNKNOWN_MACHINE"
    overlay_x = float(source.get("overlay_x", source.get("overlay_um", 0.0)) or 0.0)
    overlay_y = float(source.get("overlay_y", source.get("alignment_um", 0.0)) or 0.0)
    valid_x = bool(source.get("overlay_valid_x", True))
    valid_y = bool(source.get("overlay_valid_y", True))
    magnitude = (overlay_x**2 + overlay_y**2) ** 0.5
    source.pop("overlay_um", None)
    source.pop("alignment_um", None)
    source.pop("defect_density", None)
    source.update({
        "wafer_id": str(wafer_id),
        "lot_id": lot_id,
        "layer_id": layer_id,
        "machine": str(machine),
        "overlay_x_um": round(overlay_x, 4),
        "overlay_y_um": round(overlay_y, 4),
        "overlay_valid_x": valid_x,
        "overlay_valid_y": valid_y,
        "overlay_magnitude_um": round(magnitude, 4),
    })
    return source


def normalize_wafer_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    filters: Mapping[str, Any] | None = None,
    anomaly_threshold_um: float = 0.20,
) -> dict[str, Any]:
    active_filters = dict(filters or {})
    normalized = [
        normalize_wafer_row(row)
        for row in rows
        if _matches(row, active_filters)
    ]
    anomalous = list(dict.fromkeys(
        row["wafer_id"]
        for row in normalized
        if row.get("overlay_valid_x", True)
        and row.get("overlay_valid_y", True)
        and row.get("overlay_magnitude_um", 0) > anomaly_threshold_um
    ))
    return {"rows": normalized, "anomalous_wafers": anomalous}


def _matches(row, filters):
    candidates = {
        "machine": ("exposureprocessjob_equipment_equipmentid", "machine", "exposureEquipmentId"),
        "lot_id": ("exposureprocessjob_lotid", "lot_id", "lotId"),
        "layer_id": ("measureprocessjob_layerid", "layer_id", "layerId"),
    }
    for key, names in candidates.items():
        expected = filters.get(key)
        if not expected:
            continue
        actual = next((row.get(name) for name in names if row.get(name) is not None), None)
        if str(actual or "").lower() != str(expected).lower():
            return False
    lot_ids = filters.get("lot_ids")
    if lot_ids:
        actual = next((row.get(name) for name in candidates["lot_id"] if row.get(name) is not None), None)
        if str(actual or "").lower() not in {str(value).lower() for value in lot_ids}:
            return False
    return True
