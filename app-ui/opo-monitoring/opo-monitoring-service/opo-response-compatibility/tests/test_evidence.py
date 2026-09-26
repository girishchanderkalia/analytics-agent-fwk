from opo_response_compatibility import EVIDENCE_FIELDS, build_evidence


def test_evidence_field_set_matches_legacy_contract() -> None:
    evidence = build_evidence({})
    assert tuple(evidence) == EVIDENCE_FIELDS
    assert len(evidence) == 28


def test_evidence_maps_nested_and_renamed_fields() -> None:
    state = {
        "selected": {"machine": "M1"},
        "wafer_data": {
            "anomalous_wafers": ["W1"],
            "rows": [{"wafer_id": "W1"}],
        },
        "trend_series": [{"machine": "M1"}],
        "outliers": [{"machine": "M1"}],
    }
    evidence = build_evidence(state)
    assert evidence["selected_outlier"] == {"machine": "M1"}
    assert evidence["anomalous_wafers"] == ["W1"]
    assert evidence["wafer_rows"] == [{"wafer_id": "W1"}]
    assert evidence["trend_series"] == [{"machine": "M1"}]


def test_invalid_wafer_data_does_not_break_response() -> None:
    evidence = build_evidence({"wafer_data": "unexpected"})
    assert evidence["anomalous_wafers"] is None
    assert evidence["wafer_rows"] is None
