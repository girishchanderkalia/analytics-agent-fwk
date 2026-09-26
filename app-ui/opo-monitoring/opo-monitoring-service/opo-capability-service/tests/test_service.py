from opo_capability_service.service import OpoCapabilityService

def test_analyze_trends_delegates_to_pure_logic():
    result=OpoCapabilityService().invoke("analyze_trends",{"series":[{"series_key":{"machine":"M1"},"points":[{"kpi_value":10.0,"date":"2026-01-01","lot_id":"L1"},{"kpi_value":8.0,"date":"2026-01-02","lot_id":"L2"}]}],"mode":"absolute","limit_value":9.0,"limit_unit":"absolute"})
    assert len(result["analysis"])==1

def test_normalize_evidence():
    result=OpoCapabilityService().invoke("normalize_wafer_evidence",{"rows":[{"wafer_id":"W1","machine":"M1","overlay_x":0.3,"overlay_y":0.0}]})
    assert result["anomalous_wafers"]==["W1"]

def test_classify_pattern():
    result=OpoCapabilityService().invoke("classify_spatial_pattern",{"rows":[{"wafer_id":"W1","position_x":10,"position_y":0}],"anomalous_wafer_ids":["W1"]})
    assert result["pattern"]=="edge-concentrated"
