"""Tests for declarative Pydantic contract generation."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError


V3_ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"
OPO_AGENT_ROOT = (
    V3_ROOT
    / "agents"
    / "opo-monitoring"
)

agent_runtime_path = str(AGENT_RUNTIME_ROOT)

if agent_runtime_path not in sys.path:
    sys.path.insert(0, agent_runtime_path)


from execution.contract_factory import (  # noqa: E402
    ContractFactory,
    ContractFactoryError,
)
from execution.definition_loader import (  # noqa: E402
    load_agent_definition,
)


@pytest.fixture
def factory() -> ContractFactory:
    bundle = load_agent_definition(OPO_AGENT_ROOT)
    return ContractFactory(bundle)


def test_generates_all_declared_contracts(
    factory: ContractFactory,
) -> None:
    contracts = factory.build_all()

    assert set(contracts) == {
        "TrendFilters",
        "DetectionScope",
        "FindingsSummary",
    }


def test_contract_is_cached(
    factory: ContractFactory,
) -> None:
    first = factory.build("TrendFilters")
    second = factory.build("TrendFilters")

    assert first is second


def test_unknown_contract_is_rejected(
    factory: ContractFactory,
) -> None:
    with pytest.raises(
        ContractFactoryError,
        match="Unknown contract",
    ):
        factory.build("UnknownContract")


def test_trend_filters_defaults(
    factory: ContractFactory,
) -> None:
    TrendFilters = factory.build("TrendFilters")

    result = TrendFilters()

    assert result.lookback_days is None
    assert result.start_date is None
    assert result.end_date is None
    assert result.lot_ids == []
    assert result.product_ids == []
    assert result.layer_ids == []
    assert result.exposure_equipment_ids == []
    assert result.interpretation == ""


def test_trend_filters_accept_valid_values(
    factory: ContractFactory,
) -> None:
    TrendFilters = factory.build("TrendFilters")

    result = TrendFilters(
        lookback_days=7,
        lot_ids=["LOT-1", "LOT-2"],
        product_ids=["PRODUCT-A"],
        layer_ids=["L3"],
        exposure_equipment_ids=["0004"],
        interpretation="Last seven days for selected lot",
    )

    assert result.lookback_days == 7
    assert result.lot_ids == ["LOT-1", "LOT-2"]
    assert result.product_ids == ["PRODUCT-A"]
    assert result.layer_ids == ["L3"]
    assert result.exposure_equipment_ids == ["0004"]


def test_optional_fields_accept_none(
    factory: ContractFactory,
) -> None:
    TrendFilters = factory.build("TrendFilters")

    result = TrendFilters(
        lookback_days=None,
        start_date=None,
        end_date=None,
    )

    assert result.lookback_days is None
    assert result.start_date is None
    assert result.end_date is None


def test_list_defaults_are_independent(
    factory: ContractFactory,
) -> None:
    TrendFilters = factory.build("TrendFilters")

    first = TrendFilters()
    second = TrendFilters()

    first.lot_ids.append("LOT-1")

    assert first.lot_ids == ["LOT-1"]
    assert second.lot_ids == []


def test_detection_scope_defaults(
    factory: ContractFactory,
) -> None:
    DetectionScope = factory.build("DetectionScope")

    result = DetectionScope()

    assert result.mode == "baseline"
    assert result.limit_value == 3.0
    assert result.direction == "below"
    assert result.threshold_unit == "percent"
    assert result.baseline_deviation_pct is None
    assert result.interpretation == ""


def test_detection_scope_accepts_valid_literals(
    factory: ContractFactory,
) -> None:
    DetectionScope = factory.build("DetectionScope")

    result = DetectionScope(
        mode="absolute",
        limit_value=2.5,
        direction="above",
        threshold_unit="absolute",
    )

    assert result.mode == "absolute"
    assert result.direction == "above"
    assert result.threshold_unit == "absolute"


def test_invalid_literal_is_rejected(
    factory: ContractFactory,
) -> None:
    DetectionScope = factory.build("DetectionScope")

    with pytest.raises(ValidationError):
        DetectionScope(
            mode="unsupported",
        )


def test_findings_summary_defaults(
    factory: ContractFactory,
) -> None:
    FindingsSummary = factory.build("FindingsSummary")

    result = FindingsSummary()

    assert result.finding == ""
    assert result.evidence_references == []
    assert result.confidence == "low"
    assert result.limitations == []
    assert result.recommended_next_actions == []
    assert result.alternative_explanations == []


def test_findings_summary_accepts_valid_values(
    factory: ContractFactory,
) -> None:
    FindingsSummary = factory.build("FindingsSummary")

    result = FindingsSummary(
        finding="A consistent pattern is present.",
        evidence_references=[
            "trend_series",
            "wafer_rows",
        ],
        confidence="medium",
        limitations=[
            "Root cause is not established."
        ],
        recommended_next_actions=[
            "Compare additional wafers."
        ],
        alternative_explanations=[
            "Measurement variation."
        ],
    )

    assert result.confidence == "medium"
    assert result.evidence_references == [
        "trend_series",
        "wafer_rows",
    ]


def test_extra_fields_are_rejected(
    factory: ContractFactory,
) -> None:
    TrendFilters = factory.build("TrendFilters")

    with pytest.raises(ValidationError):
        TrendFilters(
            unknown_field="not allowed",
        )


def test_factory_validates_payload(
    factory: ContractFactory,
) -> None:
    result = factory.validate(
        "TrendFilters",
        {
            "lookback_days": 14,
            "lot_ids": ["LOT-14"],
        },
    )

    assert result.lookback_days == 14
    assert result.lot_ids == ["LOT-14"]


def test_factory_rejects_invalid_payload(
    factory: ContractFactory,
) -> None:
    with pytest.raises(ValidationError):
        factory.validate(
            "DetectionScope",
            {
                "mode": "invalid",
            },
        )


def test_generates_json_schema_for_all_contracts(
    factory: ContractFactory,
) -> None:
    schemas = factory.schemas()

    assert set(schemas) == {
        "TrendFilters",
        "DetectionScope",
        "FindingsSummary",
    }

    assert schemas["TrendFilters"]["title"] == (
        "TrendFilters"
    )

    assert "properties" in schemas["TrendFilters"]
    assert "lot_ids" in schemas["TrendFilters"]["properties"]


def test_schema_contains_field_description(
    factory: ContractFactory,
) -> None:
    schema = factory.describe(
        "TrendFilters"
    ).json_schema()

    lookback_schema = schema["properties"]["lookback_days"]

    assert lookback_schema["description"] == (
        "Relative lookback period in days."
    )


def test_literal_annotation_contains_declared_values(
    factory: ContractFactory,
) -> None:
    DetectionScope = factory.build("DetectionScope")

    annotation = DetectionScope.model_fields[
        "mode"
    ].annotation

    assert set(get_args(annotation)) == {
        "absolute",
        "baseline",
    }


def test_invalid_declared_field_type_is_rejected(
    factory: ContractFactory,
) -> None:
    factory.bundle.agent.metadata["models"][
        "TrendFilters"
    ]["fields"]["lookback_days"]["type"] = (
        "unsupported_type"
    )

    with pytest.raises(
        ContractFactoryError,
        match="unsupported type",
    ):
        factory.build("TrendFilters")


def test_literal_without_values_is_rejected(
    factory: ContractFactory,
) -> None:
    factory.bundle.agent.metadata["models"][
        "DetectionScope"
    ]["fields"]["mode"]["values"] = []

    with pytest.raises(
        ContractFactoryError,
        match="non-empty values list",
    ):
        factory.build("DetectionScope")