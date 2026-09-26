from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def classify_wafer_spatial_pattern(
    rows: Sequence[Mapping[str, Any]],
    anomalous_wafer_ids: Sequence[str],
) -> dict[str, Any]:
    """Classify anomalous points by radial position, without Foundation access."""
    all_radii = [_radius(row) for row in rows]
    wafer_radius = max(all_radii) if all_radii else 0.0
    edge_threshold = wafer_radius * 0.7
    anomalous = set(anomalous_wafer_ids)
    radii = [_radius(row) for row in rows if row.get("wafer_id") in anomalous]
    if not radii:
        return _result(0, 0, 0, None, wafer_radius, edge_threshold, "no_data")
    edge_count = sum(radius >= edge_threshold for radius in radii)
    center_count = len(radii) - edge_count
    pattern = "edge-concentrated" if edge_count > center_count else "center-concentrated" if center_count > edge_count else "mixed"
    return _result(
        len(radii), edge_count, center_count,
        round(edge_count / len(radii), 3),
        wafer_radius, edge_threshold, pattern,
    )


def _radius(row):
    x = (row.get("exposureprocessjob_waferexposureprocessjob_exposurelogicalwafer_exposedfield_field_center_x", 0.0) or 0.0) + (row.get("measureprocessjob_wafermeasureprocessjob_measurement_intrafieldposition_position_x", row.get("position_x", 0.0)) or 0.0)
    y = (row.get("exposureprocessjob_waferexposureprocessjob_exposurelogicalwafer_exposedfield_field_center_y", 0.0) or 0.0) + (row.get("measureprocessjob_wafermeasureprocessjob_measurement_intrafieldposition_position_y", row.get("position_y", 0.0)) or 0.0)
    return (float(x) ** 2 + float(y) ** 2) ** 0.5


def _result(points, edge, center, fraction, radius, threshold, pattern):
    return {
        "anomalous_point_count": points,
        "edge_count": edge,
        "center_count": center,
        "edge_fraction": fraction,
        "wafer_radius_estimate_um": round(radius, 3),
        "edge_threshold_um": round(threshold, 3),
        "pattern": pattern,
    }
