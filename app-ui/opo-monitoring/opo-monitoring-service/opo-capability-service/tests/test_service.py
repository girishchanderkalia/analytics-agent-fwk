from opo_capability_service.service import OpoCapabilityService

def test_normalize_trend_window_overrides_model_end_date_and_preserves_scope():
    filters = {"start_date": "2026-08-17", "end_date": "2026-09-30", "product_ids": ["A"], "exposure_equipment_ids": ["1234"]}
    result = OpoCapabilityService().invoke("normalize_trend_window", {"filters": filters})
    assert result["trend_filters"] == {**filters, "end_date": "2026-09-16", "lookback_days": None}

def test_normalize_trend_window_across_year_boundary():
    result = OpoCapabilityService().invoke("normalize_trend_window", {"filters": {"start_date": "2026-12-17"}})
    assert result["trend_filters"]["end_date"] == "2027-01-16"

def test_yearless_request_cannot_borrow_a_year_from_unrelated_data():
    result = OpoCapabilityService().invoke("normalize_trend_window", {
        "filters": {"start_date": "2023-08-17", "product_ids": ["A"], "layer_ids": ["abcd"], "exposure_equipment_ids": ["1234"]},
        "question": "OPO performance of product A, layer abcd on scanner 1234 since 17 Aug",
        "available_scopes": [{"product": "Product4", "layer": "L4", "scanner": "0005", "months": ["2026-09"]}],
    })
    assert result["trend_filters"]["start_date"] is None
    assert result["trend_filters"]["end_date"] is None

def test_yearless_request_uses_matching_scope_even_if_model_selects_wrong_year():
    result = OpoCapabilityService().invoke("normalize_trend_window", {
        "filters": {"start_date": "2023-08-17", "product_ids": ["A"], "layer_ids": ["abcd"], "exposure_equipment_ids": ["1234"]},
        "question": "OPO performance of product A, layer abcd on scanner 1234 since 17 Aug",
        "available_scopes": [{"product": "A", "layer": "abcd", "scanner": "1234", "months": ["2026-09"]}],
    })
    assert result["trend_filters"]["start_date"] == "2026-08-17"
    assert result["trend_filters"]["end_date"] == "2026-09-16"

def test_analyze_trends_delegates_to_pure_logic():
    result=OpoCapabilityService().invoke("analyze_trends",{"series":[{"series_key":{"machine":"M1"},"points":[{"kpi_value":10.0,"date":"2026-01-01","lot_id":"L1"},{"kpi_value":8.0,"date":"2026-01-02","lot_id":"L2"}]}],"mode":"absolute","limit_value":9.0,"limit_unit":"absolute"})
    assert len(result["analysis"])==1

def test_normalize_evidence():
    result=OpoCapabilityService().invoke("normalize_wafer_evidence",{"rows":[{"wafer_id":"W1","machine":"M1","overlay_x":0.3,"overlay_y":0.0}]})
    assert result["anomalous_wafers"]==["W1"]

def test_classify_pattern():
    result=OpoCapabilityService().invoke("classify_spatial_pattern",{"rows":[{"wafer_id":"W1","position_x":10,"position_y":0}],"anomalous_wafer_ids":["W1"]})
    assert result["pattern"]=="edge-concentrated"
