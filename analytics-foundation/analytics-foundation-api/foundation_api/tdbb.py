"""Mock TDBB runs backed by the synthetic overlay source.

The run index (data/tdbb_runs_v3.json) lists one completed run per lot, like the
real run. Run data follows the real TDBB tables (ce_wafer, ce_field, nce_wafer,
nce_field) with AVG per lot and W2W per wafer; values are regenerated
deterministically, so they are not stored. The overview reports |mean|+3 sigma
in nm per metric (columns) and context level (rows), like the TDBB Overview.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from .synthetic_overlay import INTRAFIELD_POSITIONS, profile_for, wafer_points

METRICS = (
    ("nce_wafer", "NCE - Wafer"),
    ("nce_field", "NCE - Field"),
    ("ce_wafer", "CE - Wafer"),
    ("ce_field", "CE - Field"),
    ("ce_translation", "CE - Translation"),
)
CONTEXTS = (
    ("average", "Average"),
    ("chuck_to_chuck", "Chuck to chuck"),
    ("lot_to_lot", "Lot to lot"),
    ("wafer_to_wafer", "Wafer to wafer"),
)
BUDGETS = tuple(f"{metric}.{context}" for context, _ in CONTEXTS for metric, _ in METRICS)
_MAP_LEVELS = {"nce_wafer": "wafer", "ce_wafer": "wafer", "nce_field": "field", "ce_field": "field"}
TABLES = ("ce_wafer", "ce_field", "nce_wafer", "nce_field")
_AVERAGED = ("ce_translation_x", "ce_translation_y", "ce_wafer_x", "ce_wafer_y", "ce_field_x", "ce_field_y", "nce_x", "nce_y", "overlay_x", "overlay_y")


class _Stats:
    __slots__ = ("n", "sx", "sxx", "sy", "syy")

    def __init__(self) -> None:
        self.n = 0
        self.sx = self.sxx = self.sy = self.syy = 0.0

    def add(self, x: float, y: float) -> None:
        self.n += 1
        self.sx += x
        self.sxx += x * x
        self.sy += y
        self.syy += y * y

    def mean(self) -> tuple[float, float]:
        return self.sx / self.n, self.sy / self.n

    def m3s(self) -> tuple[float | None, float | None]:
        if self.n < 2:
            return None, None
        return _m3s(self.n, self.sx, self.sxx), _m3s(self.n, self.sy, self.syy)


def _m3s(n: int, total: float, squares: float) -> float:
    average = total / n
    variance = max(0.0, (squares - n * average * average) / (n - 1))
    return round(abs(average) + 3 * math.sqrt(variance), 3)


def _lot(run: Mapping[str, Any], chuck_ids: Iterable[str] = ()) -> tuple[list[Mapping[str, Any]], list[list[dict[str, float]]]]:
    """Return the run's wafers and their synthetic points, optionally limited to chucks."""

    profile = profile_for(run["product_id"], run["layer_id"], run["exposure_equipment_id"])
    chucks = set(chuck_ids)
    wafers = [w for w in run["wafers"] if not chucks or w["chuck_id"] in chucks]
    if profile is None:
        return [], []
    return wafers, [wafer_points(run["lot_id"], w["wafer_id"], w["chuck_id"], run["lot_start"], profile) for w in wafers]


def _average(points_by_wafer: list[list[dict[str, float]]]) -> list[dict[str, float]]:
    count = len(points_by_wafer)
    return [
        {**points[0], **{name: sum(p[name] for p in points) / count for name in _AVERAGED}}
        for points in zip(*points_by_wafer)
    ]


def _mean(values: list[tuple[float, float]]) -> tuple[float, float]:
    return sum(v[0] for v in values) / len(values), sum(v[1] for v in values) / len(values)


def _metric_values(points: list[dict[str, float]]) -> dict[str, tuple[list[tuple[float, float]], list[tuple[float, float] | None]]]:
    """Per metric: the wafer's values and their map locations (field center, intrafield position, or none)."""

    by_position: dict[tuple[float, float], list[dict[str, float]]] = defaultdict(list)
    for point in points:
        by_position[(point["intrafield_position_x"], point["intrafield_position_y"])].append(point)
    positions = list(INTRAFIELD_POSITIONS)
    centers = [(p["field_center_x"], p["field_center_y"]) for p in points]
    field = lambda component: [_mean([(p[f"{component}_x"], p[f"{component}_y"]) for p in by_position[pos]]) for pos in positions]
    return {
        "nce_wafer": ([(p["nce_x"], p["nce_y"]) for p in points], centers),
        "nce_field": (field("nce"), positions),
        "ce_wafer": ([(p["ce_wafer_x"], p["ce_wafer_y"]) for p in points], centers),
        "ce_field": (field("ce_field"), positions),
        "ce_translation": ([(points[0]["ce_translation_x"], points[0]["ce_translation_y"])], [None]),
    }


def process_period(runs: Iterable[Mapping[str, Any]], chuck_ids: Iterable[str] = ()) -> dict[str, Any]:
    """Aggregate the given runs into the TDBB overview (metric x context level) and wafer/field maps.

    Average is the lot average over wafers; chuck to chuck, wafer to wafer and lot to lot are the
    deviations of chuck, wafer and lot averages from the lot average and the period average.
    """

    budgets = {(metric, context): _Stats() for metric, _ in METRICS for context, _ in CONTEXTS}
    maps = {key: defaultdict(_Stats) for key in budgets}

    def add(metric: str, context: str, location: tuple[float, float] | None, x: float, y: float) -> None:
        budgets[(metric, context)].add(x, y)
        if location is not None:
            maps[(metric, context)][location].add(x, y)

    lot_averages: dict[str, list[list[tuple[float, float]]]] = defaultdict(list)
    locations: dict[str, list[tuple[float, float] | None]] = {}
    lot_count = wafer_count = 0
    for run in runs:
        wafers, points_by_wafer = _lot(run, chuck_ids)
        if not wafers:
            continue
        lot_count += 1
        wafer_count += len(wafers)
        per_wafer = [_metric_values(points) for points in points_by_wafer]
        for metric, _ in METRICS:
            values = [wafer[metric][0] for wafer in per_wafer]
            locations[metric] = per_wafer[0][metric][1]
            average = [_mean(list(column)) for column in zip(*values)]
            lot_averages[metric].append(average)
            chucks: dict[Any, list[list[tuple[float, float]]]] = defaultdict(list)
            for wafer, wafer_values in zip(wafers, values):
                chucks[wafer.get("chuck_id")].append(wafer_values)
            for index, (ax, ay) in enumerate(average):
                location = locations[metric][index]
                add(metric, "average", location, ax, ay)
                for wafer_values in values:
                    add(metric, "wafer_to_wafer", location, wafer_values[index][0] - ax, wafer_values[index][1] - ay)
                for chuck_values in chucks.values():
                    cx, cy = _mean([wafer_values[index] for wafer_values in chuck_values])
                    add(metric, "chuck_to_chuck", location, cx - ax, cy - ay)

    for metric, averages in lot_averages.items():
        period = [_mean(list(column)) for column in zip(*averages)]
        for average in averages:
            for index, ((ax, ay), (px, py)) in enumerate(zip(average, period)):
                add(metric, "lot_to_lot", locations[metric][index], ax - px, ay - py)

    summary = []
    for context, context_label in CONTEXTS:
        for metric, metric_label in METRICS:
            x_m3s, y_m3s = budgets[(metric, context)].m3s()
            summary.append({
                "budget": f"{metric}.{context}",
                "label": f"{metric_label} · {context_label}",
                "metric": metric,
                "metric_label": metric_label,
                "context": context,
                "context_label": context_label,
                "x_m3s": x_m3s,
                "y_m3s": y_m3s,
            })
    return {
        "lot_count": lot_count,
        "wafer_count": wafer_count,
        "budgets": summary,
        "maps": {
            f"{metric}.{context}": {_MAP_LEVELS[metric]: _map_points(maps[(metric, context)])}
            for metric, context in budgets
            if metric in _MAP_LEVELS
        },
    }


def run_rows(run: Mapping[str, Any], tables: Iterable[str] = TABLES) -> dict[str, list[dict[str, Any]]]:
    """Return one run's rows in the real TDBB table schema."""

    wafers, points_by_wafer = _lot(run)
    if not wafers:
        return {table: [] for table in tables}
    averages = _average(points_by_wafer)
    contexts = [("AVG", "1", None, averages)] + [
        ("W2W", str(index + 2), wafer, [
            {**point, **{name: point[name] - average[name] for name in _AVERAGED}}
            for point, average in zip(points, averages)
        ])
        for index, (wafer, points) in enumerate(zip(wafers, points_by_wafer))
    ]
    result: dict[str, list[dict[str, Any]]] = {}
    for table in tables:
        rows = []
        for context_level, dataset, wafer, points in contexts:
            base = {
                "run_id": run["run_id"],
                "context_level": context_level,
                "virtual_dataset_id": dataset,
                "model_step": "10par" if table.startswith("ce_") else None,
                "model_step_number": "0" if table.startswith("ce_") else None,
                "image_width": 26.0,
                "image_height": 33.0,
                "chuck_id": wafer["chuck_id"] if wafer else None,
                "lot_id": run["lot_id"],
                "lot_start": run["lot_start"],
                "equipment_id": run["exposure_equipment_id"],
                "wafer_id": wafer["wafer_id"] if wafer else None,
            }
            if table.startswith("ce_"):
                base["order"] = None
            if table.endswith("_wafer"):
                rows.extend(_wafer_row(table, base, point) for point in points)
            else:
                rows.extend(_field_rows(table, base, points))
        result[table] = rows
    return result


def _wafer_row(table: str, base: Mapping[str, Any], point: Mapping[str, float]) -> dict[str, Any]:
    row = {
        **base,
        "field_center_x": point["field_center_x"],
        "field_center_y": point["field_center_y"],
        "intrafield_position_x": point["intrafield_position_x"],
        "intrafield_position_y": point["intrafield_position_y"],
        "wafer_diameter": 300.0,
    }
    if table == "ce_wafer":
        row.update({
            "ce_translation_x": round(point["ce_translation_x"], 6),
            "ce_translation_y": round(point["ce_translation_y"], 6),
            "ce_wafer_x": round(point["ce_wafer_x"], 6),
            "ce_wafer_y": round(point["ce_wafer_y"], 6),
            "ce_susd_x": None,
            "ce_susd_y": None,
        })
    else:
        row.update({
            "nce_wafer_x": round(point["nce_x"], 6),
            "nce_wafer_y": round(point["nce_y"], 6),
            "nce_susd_x": None,
            "nce_susd_y": None,
        })
    return row


def _field_rows(table: str, base: Mapping[str, Any], points: list[Mapping[str, float]]) -> list[dict[str, Any]]:
    component = "ce_field" if table == "ce_field" else "nce"
    rows = []
    for intra_x, intra_y in INTRAFIELD_POSITIONS:
        matching = [p for p in points if p["intrafield_position_x"] == intra_x and p["intrafield_position_y"] == intra_y]
        rows.append({
            **base,
            "intrafield_position_x": intra_x,
            "intrafield_position_y": intra_y,
            f"{table}_x": round(sum(p[f"{component}_x"] for p in matching) / len(matching), 6),
            f"{table}_y": round(sum(p[f"{component}_y"] for p in matching) / len(matching), 6),
        })
    return rows


def _map_points(locations: Mapping[tuple[float, float], _Stats]) -> list[dict[str, float | None]]:
    points = []
    for (x, y), stats in sorted(locations.items()):
        dx, dy = stats.mean()
        m3s_x, m3s_y = stats.m3s()
        points.append({"x": x, "y": y, "dx": round(dx, 4), "dy": round(dy, 4), "m3s_x": m3s_x, "m3s_y": m3s_y})
    return points
