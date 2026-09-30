from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

_MIN_DAYS = 3
# Below this the daily means show no clear step, so nothing is suggested.
_MIN_T = 4.0


def suggest_change_date(series: Sequence[Mapping[str, Any]], end_date: str | None = None) -> dict[str, Any]:
    """Suggest the day the overlay X/Y KPIs stepped, from daily means of the trend points.

    The split maximizes Welch's t-statistic between the days before and from the
    change date, with at least three days on each side.
    """

    daily: dict[str, list[float]] = defaultdict(list)
    for item in series:
        for point in item.get("points", []):
            values = [point.get(key) for key in ("kpi_value", "kpi_value_y")]
            values = [float(v) for v in values if v is not None]
            if values:
                daily[str(point["date"])[:10]].append(sum(values) / len(values))
    days = sorted(daily)
    means = [sum(daily[day]) / len(daily[day]) for day in days]

    best = None
    for split in range(_MIN_DAYS, len(days) - _MIN_DAYS + 1):
        score = _welch_t(means[:split], means[split:])
        if best is None or abs(score) > abs(best[1]):
            best = (split, score)
    if best is None:
        return {"change_date": None, "question": ""}

    split, score = best
    if abs(score) < _MIN_T:
        return {"change_date": None, "t_statistic": round(score, 2), "question": ""}
    before, after = means[:split], means[split:]
    change = date.fromisoformat(days[split])
    until = date.fromisoformat(end_date) if end_date else date.fromisoformat(days[-1])
    return {
        "change_date": change.isoformat(),
        "before_mean": round(sum(before) / len(before), 3),
        "after_mean": round(sum(after) / len(after), 3),
        "t_statistic": round(score, 2),
        "question": (
            f"I observe a jump from {_day(change)} to {_day(until)}. "
            "I want to know what has been changed in OPO."
        ),
    }


def _welch_t(left: Sequence[float], right: Sequence[float]) -> float:
    def stats(values: Sequence[float]) -> tuple[float, float]:
        average = sum(values) / len(values)
        return average, sum((v - average) ** 2 for v in values) / (len(values) - 1)

    left_mean, left_var = stats(left)
    right_mean, right_var = stats(right)
    spread = math.sqrt(left_var / len(left) + right_var / len(right))
    return (right_mean - left_mean) / spread if spread else 0.0


def _day(value: date) -> str:
    return f"{value.day} {value:%b}"
