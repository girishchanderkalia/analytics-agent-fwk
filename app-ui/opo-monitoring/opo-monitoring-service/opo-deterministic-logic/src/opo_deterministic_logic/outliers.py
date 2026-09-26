from __future__ import annotations

from collections.abc import Iterable, Mapping
from statistics import median
from typing import Any


def analyse_series(
    series: Iterable[Mapping[str, Any]],
    *,
    mode: str = "baseline",
    limit_value: float | None = None,
    direction: str = "below",
    baseline_deviation_pct: float = 3.0,
    limit_unit: str = "percent",
) -> list[dict[str, Any]]:
    """Apply OPO threshold rules to already retrieved trend series."""
    if mode not in {"absolute", "baseline"}:
        raise ValueError("mode must be 'absolute' or 'baseline'")
    if direction not in {"above", "below"}:
        raise ValueError("direction must be 'above' or 'below'")
    if limit_unit not in {"percent", "absolute"}:
        raise ValueError("limit_unit must be 'percent' or 'absolute'")
    if baseline_deviation_pct < 0:
        raise ValueError("baseline_deviation_pct must be non-negative")

    analysis = []
    for raw in series:
        item = dict(raw)
        points = [dict(point) for point in item.get("points", [])]
        if not points:
            continue
        baseline = median(float(point["kpi_value"]) for point in points)
        if mode == "absolute":
            if limit_value is None:
                raise ValueError("limit_value is required in absolute mode")
            requested = float(limit_value)
            applied = requested
            if limit_unit == "percent":
                factor = 1 + requested / 100 if direction == "above" else 1 - requested / 100
                applied = baseline * factor
            predicate = (
                (lambda value: value >= applied)
                if direction == "above"
                else (lambda value: value <= applied)
            )
        else:
            applied = baseline * (1 + baseline_deviation_pct / 100)
            predicate = lambda value: value >= applied

        flagged = [
            (index, point)
            for index, point in enumerate(points)
            if predicate(float(point["kpi_value"]))
        ]
        values = [float(point["kpi_value"]) for _, point in flagged]
        extreme = None
        if values:
            extreme = max(values) if direction == "above" or mode == "baseline" else min(values)
        analysis.append({
            "machine": item.get("machine"),
            "product": item.get("product"),
            "baseline": round(baseline, 1),
            "limit_applied_value": round(applied, 2),
            "extreme_kpi_value": extreme,
            "extreme_lot_id": next(
                (point.get("lot_id") for _, point in flagged if float(point["kpi_value"]) == extreme),
                None,
            ),
            "outlier_lot_ids": list(dict.fromkeys(
                point.get("lot_id") for _, point in flagged if point.get("lot_id")
            )),
            "deviation_pct": (
                round(abs(extreme - baseline) / baseline * 100, 1)
                if extreme is not None and baseline != 0
                else 0.0
            ),
            "outlier_dates": [
                f"{index}#{point['date']}" for index, point in flagged
            ],
        })
    return analysis


def detect_outliers(
    series: Iterable[Mapping[str, Any]],
    **rules: Any,
) -> list[dict[str, Any]]:
    flagged = [item for item in analyse_series(series, **rules) if item["outlier_dates"]]
    return sorted(flagged, key=lambda item: item["deviation_pct"], reverse=True)
