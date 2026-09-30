from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def compare_tdbb_budgets(periods: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare TDBB budgets (|mean|+3 sigma, nm) after a change against before it.

    The largest increase is the largest relative change over budgets and axes.
    """

    by_period = {period.get("period"): period for period in periods}
    before = by_period.get("before") or {}
    after = by_period.get("after") or {}
    before_budgets = {item["budget"]: item for item in before.get("budgets", [])}
    rows = []
    for item in after.get("budgets", []):
        reference = before_budgets.get(item["budget"], {})
        row = {"budget": item["budget"], "label": item.get("label", item["budget"])}
        row.update({key: item[key] for key in ("metric", "metric_label", "context", "context_label") if key in item})
        for axis in ("x", "y"):
            old, new = reference.get(f"{axis}_m3s"), item.get(f"{axis}_m3s")
            row[f"before_{axis}"] = old
            row[f"after_{axis}"] = new
            row[f"delta_{axis}"] = None if old is None or new is None else round(new - old, 3)
            row[f"delta_{axis}_pct"] = None if old in (None, 0) or new is None else round((new - old) / old * 100, 1)
        rows.append(row)

    increases = [
        {"budget": row["budget"], "label": row["label"], "axis": axis.upper(), "delta": row[f"delta_{axis}"], "delta_pct": row[f"delta_{axis}_pct"]}
        for row in rows
        for axis in ("x", "y")
        if row[f"delta_{axis}_pct"] is not None and row[f"delta_{axis}"] > 0
    ]
    largest = max(increases, key=lambda item: item["delta_pct"], default=None)
    return {
        "before": _period_summary(before),
        "after": _period_summary(after),
        "budgets": rows,
        "largest_increase": largest,
        "headline": _headline(largest, rows),
    }


def _headline(largest: Mapping[str, Any] | None, rows: Sequence[Mapping[str, Any]]) -> str:
    if largest is None:
        return "No TDBB budget increased after the change date."
    row = next(item for item in rows if item["budget"] == largest["budget"])
    axis = largest["axis"].lower()
    return (
        f"Largest increase: {largest['label']} {largest['axis']} +{largest['delta_pct']}% "
        f"({row[f'before_{axis}']} \u2192 {row[f'after_{axis}']} nm)"
    )


def _period_summary(period: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "start_date": period.get("start_date"),
        "end_date": period.get("end_date"),
        "lot_count": period.get("lot_count", 0),
        "wafer_count": period.get("wafer_count", 0),
        "run_count": len(period.get("run_ids", [])),
    }
