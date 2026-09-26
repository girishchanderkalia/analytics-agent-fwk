from __future__ import annotations
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class AnalyseTrendsRequest(StrictModel):
    series: list[dict[str, Any]]
    mode: str = "baseline"
    limit_value: float | None = None
    direction: str = "below"
    baseline_deviation_pct: float = Field(default=3.0, ge=0)
    limit_unit: str = "percent"

class NormalizeWaferEvidenceRequest(StrictModel):
    rows: list[dict[str, Any]]
    filters: dict[str, Any] = Field(default_factory=dict)
    anomaly_threshold_um: float = Field(default=0.20, ge=0)

class ClassifySpatialPatternRequest(StrictModel):
    rows: list[dict[str, Any]]
    anomalous_wafer_ids: list[str]
