from datetime import date
from opo_capability_service.service import OpoCapabilityService

TODAY = lambda: date(2026, 9, 30)

def test_normalize_trend_window_overrides_model_end_date_and_preserves_scope():
    filters = {"start_date": "2026-08-17", "end_date": "2026-09-30", "product_ids": ["A"], "exposure_equipment_ids": ["1234"]}
    result = OpoCapabilityService().invoke("normalize_trend_window", {"filters": filters})
    assert result["trend_filters"] == {**filters, "end_date": "2026-09-16", "lookback_days": None}

def test_normalize_trend_window_across_year_boundary():
    result = OpoCapabilityService().invoke("normalize_trend_window", {"filters": {"start_date": "2026-12-17"}})
    assert result["trend_filters"]["end_date"] == "2027-01-16"

def test_yearless_request_uses_current_year_whatever_the_model_guessed():
    result = OpoCapabilityService(TODAY).invoke("normalize_trend_window", {
        "filters": {"start_date": "2023-08-17", "product_ids": ["AAA2"], "layer_ids": ["OV_NO_ID2"], "exposure_equipment_ids": ["GW021"]},
        "question": "OPO performance of product AAA2, layer OV_NO_ID2 on scanner GW021 since 17 Aug",
    })
    assert (result["trend_filters"]["start_date"], result["trend_filters"]["end_date"]) == ("2026-08-17", "2026-09-16")

def test_yearless_future_date_uses_previous_year():
    result = OpoCapabilityService(TODAY).invoke("normalize_trend_window", {"filters": {"start_date": "2026-11-02"}, "question": "since 2 Nov"})
    assert result["trend_filters"]["start_date"] == "2025-11-02"

def test_explicit_year_is_kept():
    result = OpoCapabilityService(TODAY).invoke("normalize_trend_window", {"filters": {"start_date": "2024-08-17"}, "question": "since 17 Aug 2024"})
    assert result["trend_filters"]["start_date"] == "2024-08-17"

def test_missing_start_date_stays_unresolved():
    result = OpoCapabilityService(TODAY).invoke("normalize_trend_window", {"filters": {"start_date": None}, "question": "show OPO"})
    assert result["trend_filters"]["start_date"] is None and result["trend_filters"]["end_date"] is None

def test_compare_tdbb_budgets_reports_deltas_and_largest_increase():
    budgets = lambda nce, w2w: [{"budget": "nce", "label": "NCE", "x_m3s": nce, "y_m3s": nce}, {"budget": "w2w", "label": "W2W", "x_m3s": w2w, "y_m3s": w2w}]
    result = OpoCapabilityService().invoke("compare_tdbb_budgets", {"periods": [
        {"period": "before", "start_date": "2026-08-17", "end_date": "2026-08-31", "run_ids": ["r1"], "lot_count": 1, "wafer_count": 8, "budgets": budgets(0.74, 1.8)},
        {"period": "after", "start_date": "2026-09-01", "end_date": "2026-09-16", "run_ids": ["r2"], "lot_count": 1, "wafer_count": 8, "budgets": budgets(1.54, 2.0)},
    ]})
    nce = result["budgets"][0]
    assert (nce["delta_x"], nce["delta_x_pct"]) == (0.8, 108.1)
    assert (result["largest_increase"]["budget"], result["largest_increase"]["axis"]) == ("nce", "X")
    assert result["after"]["run_count"] == 1

def _daily(values):
    return [{"points": [{"date": f"2026-08-{day:02d}T06:00:00+00:00", "kpi_value": value, "kpi_value_y": value + 0.1} for day, value in values]}]

def test_suggest_change_date_finds_the_step_and_prefills_the_question():
    series = _daily([(day, 2.4 + 0.02 * (day % 3)) for day in range(1, 11)] + [(day, 3.4 + 0.02 * (day % 3)) for day in range(11, 21)])
    result = OpoCapabilityService().invoke("suggest_change_date", {"series": series, "end_date": "2026-08-20"})
    assert result["change_date"] == "2026-08-11"
    assert result["question"] == "I observe a jump from 11 Aug to 20 Aug. I want to know what has been changed in OPO."

def test_suggest_change_date_stays_empty_without_a_step():
    series = _daily([(day, 2.4 + 0.05 * (day % 4)) for day in range(1, 21)])
    result = OpoCapabilityService().invoke("suggest_change_date", {"series": series})
    assert (result["change_date"], result["question"]) == (None, "")

def test_analyze_trends_delegates_to_pure_logic():
    result=OpoCapabilityService().invoke("analyze_trends",{"series":[{"series_key":{"machine":"M1"},"points":[{"kpi_value":10.0,"date":"2026-01-01","lot_id":"L1"},{"kpi_value":8.0,"date":"2026-01-02","lot_id":"L2"}]}],"mode":"absolute","limit_value":9.0,"limit_unit":"absolute"})
    assert len(result["analysis"])==1

def test_normalize_evidence():
    result=OpoCapabilityService().invoke("normalize_wafer_evidence",{"rows":[{"wafer_id":"W1","machine":"M1","overlay_x":0.3,"overlay_y":0.0}]})
    assert result["anomalous_wafers"]==["W1"]

def test_classify_pattern():
    result=OpoCapabilityService().invoke("classify_spatial_pattern",{"rows":[{"wafer_id":"W1","position_x":10,"position_y":0}],"anomalous_wafer_ids":["W1"]})
    assert result["pattern"]=="edge-concentrated"
