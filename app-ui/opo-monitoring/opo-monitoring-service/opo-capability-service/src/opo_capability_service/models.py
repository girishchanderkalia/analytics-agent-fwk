from __future__ import annotations
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class AnalyseTrendsRequest(StrictModel):
    series: list[dict[str, Any]]
    mode: str | None = "baseline"
    limit_value: float | None = None
    direction: str | None = "below"
    baseline_deviation_pct: float | None = Field(default=3.0, ge=0)
    limit_unit: str | None = "percent"

class NormalizeWaferEvidenceRequest(StrictModel):
    rows: list[dict[str, Any]]
    filters: dict[str, Any] = Field(default_factory=dict)
    anomaly_threshold_um: float = Field(default=0.20, ge=0)

class CompareTdbbBudgetsRequest(StrictModel):
    periods: list[dict[str, Any]]

class SuggestChangeDateRequest(StrictModel):
    series: list[dict[str, Any]]
    end_date: str | None = None

class ClassifySpatialPatternRequest(StrictModel):
    rows: list[dict[str, Any]]
    anomalous_wafer_ids: list[str]
