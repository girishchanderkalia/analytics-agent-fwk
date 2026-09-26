from datetime import date

import pytest

from opo_deterministic_logic import (
    analyse_series,
    build_trend_series,
    classify_wafer_spatial_pattern,
    detect_outliers,
    normalize_wafer_row,
    normalize_wafer_rows,
)


def test_build_trend_series_filters_and_sorts() -> None:
    rows = [
        {"machine": "M1", "product": "P1", "lotId": "L2", "layerId": "A", "lotStart": "2026-09-23T10:00:00", "kpiValue1": 3.2},
        {"machine": "M1", "product": "P1", "lotId": "L1", "layerId": "A", "lotStart": "2026-09-22T10:00:00", "kpiValue1": 3.0},
        {"machine": "M2", "product": "P2", "lotId": "L3", "layerId": "B", "lotStart": "2026-09-23T10:00:00", "kpiValue1": 4.0},
    ]
    result = build_trend_series(rows, days=3, exposure_equipment_ids=["M1"], today=date(2026, 9, 24))
    assert len(result) == 1
    assert [point["lot_id"] for point in result[0]["points"]] == ["L1", "L2"]


def test_explicit_date_range_wins() -> None:
    rows = [{"machine": "M1", "product": "P1", "lotStart": "2025-01-01", "kpiValue1": 3.0}]
    result = build_trend_series(rows, days=1, start_date="2025-01-01", end_date="2025-01-01", today=date(2026, 9, 24))
    assert len(result) == 1


def test_baseline_analysis_and_sorting() -> None:
    series = [
        {"machine": "M1", "product": "P1", "points": [{"date": "1", "kpi_value": 10, "lot_id": "L1"}, {"date": "2", "kpi_value": 15, "lot_id": "L2"}]},
        {"machine": "M2", "product": "P2", "points": [{"date": "1", "kpi_value": 10, "lot_id": "L3"}, {"date": "2", "kpi_value": 11, "lot_id": "L4"}]},
    ]
    result = detect_outliers(series, mode="baseline", baseline_deviation_pct=10)
    assert result[0]["machine"] == "M1"
    assert result[0]["outlier_lot_ids"] == ["L2"]


def test_absolute_below_rule() -> None:
    series = [{"machine": "M1", "product": "P1", "points": [{"date": "1", "kpi_value": 2, "lot_id": "L1"}, {"date": "2", "kpi_value": 5, "lot_id": "L2"}]}]
    result = analyse_series(series, mode="absolute", limit_value=3, direction="below", limit_unit="absolute")
    assert result[0]["extreme_kpi_value"] == 2


def test_invalid_rule_is_rejected() -> None:
    with pytest.raises(ValueError):
        analyse_series([], mode="unknown")


def test_normalize_wafer_row() -> None:
    row = normalize_wafer_row({"waferId": "W1", "overlay_x": 0.3, "overlay_y": 0.4})
    assert row["wafer_id"] == "W1"
    assert row["overlay_magnitude_um"] == 0.5


def test_normalize_rows_filters_and_finds_anomalies() -> None:
    result = normalize_wafer_rows([
        {"waferId": "W1", "machine": "M1", "overlay_x": 0.3},
        {"waferId": "W2", "machine": "M2", "overlay_x": 0.5},
    ], filters={"machine": "M1"})
    assert [row["wafer_id"] for row in result["rows"]] == ["W1"]
    assert result["anomalous_wafers"] == ["W1"]


def test_spatial_classification() -> None:
    rows = [
        {"wafer_id": "W1", "position_x": 10, "position_y": 0},
        {"wafer_id": "W1", "position_x": 9, "position_y": 0},
        {"wafer_id": "W2", "position_x": 1, "position_y": 0},
    ]
    result = classify_wafer_spatial_pattern(rows, ["W1"])
    assert result["pattern"] == "edge-concentrated"
    assert result["edge_fraction"] == 1.0


def test_spatial_no_data() -> None:
    result = classify_wafer_spatial_pattern([], [])
    assert result["pattern"] == "no_data"
