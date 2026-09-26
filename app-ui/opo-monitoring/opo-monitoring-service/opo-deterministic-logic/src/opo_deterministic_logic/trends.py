from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Any


def build_trend_series(
    rows: Iterable[Mapping[str, Any]],
    *,
    days: int | None = 14,
    start_date: str | None = None,
    end_date: str | None = None,
    lot_ids: Sequence[str] | None = None,
    product_ids: Sequence[str] | None = None,
    layer_ids: Sequence[str] | None = None,
    exposure_equipment_ids: Sequence[str] | None = None,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Filter and group Foundation trend rows without data access."""
    range_start, range_end = _date_range(
        days=days,
        start_date=start_date,
        end_date=end_date,
        today=today or date.today(),
    )
    lots = _normalized_set(lot_ids)
    products = _normalized_set(product_ids)
    layers = _normalized_set(layer_ids)
    machines = _normalized_set(exposure_equipment_ids)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for source in rows:
        item = dict(source)
        machine, product = _series_identity(item)
        lot_id = item.get("lotId", item.get("lot_id"))
        layer_id = item.get("layerId", item.get("layer_id"))
        exposure_id = item.get("exposureEquipmentId", machine)
        if machines and machine.lower() not in machines:
            continue
        if lots and str(lot_id or "").lower() not in lots:
            continue
        if products and product.lower() not in products:
            continue
        if layers and str(layer_id or "").lower() not in layers:
            continue
        timestamp = _timestamp(item.get("lotStart", item.get("lot_start")))
        value = item.get("kpiValue1", item.get("kpi_value"))
        if timestamp is None or value is None:
            continue
        if timestamp.date() < range_start or timestamp.date() > range_end:
            continue
        key = (machine, product)
        series = grouped.setdefault(key, {
            "machine": machine,
            "product": product,
            "lot_id": lot_id,
            "layer_id": layer_id,
            "exposure_equipment_id": exposure_id,
            "points": [],
        })
        series["points"].append({
            "date": timestamp.isoformat(),
            "kpi_value": round(float(value), 2),
            "lot_id": lot_id,
        })

    result = list(grouped.values())
    for series in result:
        series["points"].sort(key=lambda point: point["date"])
    result.sort(key=lambda series: (series["machine"], series["product"]))
    return result


def _date_range(*, days, start_date, end_date, today):
    if start_date or end_date:
        return (
            date.fromisoformat(start_date) if start_date else date.min,
            date.fromisoformat(end_date) if end_date else date.max,
        )
    if days is None:
        return date.min, date.max
    if days < 1:
        raise ValueError("days must be positive")
    return today - timedelta(days=days - 1), date.max


def _normalized_set(values):
    return {str(value).strip().lower() for value in values or () if str(value).strip()}


def _series_identity(item):
    machine = item.get("machine") or item.get("exposureEquipmentId") or item.get("machineId") or "UNKNOWN_MACHINE"
    product = item.get("product") or item.get("productId") or item.get("layerId") or "UNKNOWN_PRODUCT"
    return str(machine), str(product)


def _timestamp(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
