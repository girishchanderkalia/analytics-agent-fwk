"""Models aligned with the Slice 13A OpenAPI contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictModel):
    status: Literal["ok"]


class DatasetMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    trend_table: str
    wafer_table: str


class TrendQueryRequest(StrictModel):
    days: int | None = Field(default=None, ge=1, le=90)
    start_date: str | None = None
    end_date: str | None = None
    lot_ids: list[str] = Field(default_factory=list)
    product_ids: list[str] = Field(default_factory=list)
    layer_ids: list[str] = Field(default_factory=list)
    exposure_equipment_ids: list[str] = Field(default_factory=list)
    chuck_ids: list[str] = Field(default_factory=list)


class TrendPoint(StrictModel):
    date: str
    kpi_value: float
    kpi_value_y: float | None = None
    lot_id: str | None = None
    wafer_id: str | None = None
    chuck_id: str | None = None


class TrendSeries(StrictModel):
    machine: str
    product: str
    lot_id: str | None = None
    layer_id: str | None = None
    exposure_equipment_id: str | None = None
    points: list[TrendPoint]


class TrendResponse(StrictModel):
    series: list[TrendSeries]


class BellCurveRange(StrictModel):
    lower: float
    upper: float


class DistributionStats(StrictModel):
    sample_count: int = Field(ge=0)
    p95: float | None = None
    p99: float | None = None
    mean: float | None = None
    stdev: float | None = None
    bell_curve_range: BellCurveRange | None = None


class WorkspaceResponse(StrictModel):
    workspace_id: str


class WorkspaceFiltersRequest(StrictModel):
    filters: dict[str, Any]


class WorkspaceFiltersResponse(StrictModel):
    workspace_id: str
    filters: dict[str, Any]


class WorkspaceConnectionInfo(StrictModel):
    workspace_id: str
    values: dict[str, Any]


class RegistrationRequest(StrictModel):
    dataset: str
    table: str


class RegistrationStatus(StrictModel):
    registration_id: str
    workspace_id: str
    status: Literal["PENDING", "RUNNING", "READY", "FAILED"]
    progress_pct: int = Field(ge=0, le=100)
    table: str
    error: str | None = None


class WaferQueryRequest(StrictModel):
    workspace_id: str
    table: str
    filters: dict[str, Any] = Field(default_factory=dict)


class WaferQueryResponse(StrictModel):
    workspace_id: str
    table: str
    rows: list[dict[str, Any]]
    anomalous_wafers: list[str]


class TdbbRunRequest(TrendQueryRequest):
    start_date: str
    end_date: str
    change_date: str
    model_step: Literal["10par"] = "10par"
    context_levels: list[Literal["AVG", "W2W"]] = Field(default_factory=lambda: ["AVG", "W2W"])


class TdbbCompareRequest(StrictModel):
    before_run_ids: list[str] = Field(default_factory=list)
    after_run_ids: list[str] = Field(default_factory=list)


class TdbbSettings(StrictModel):
    model_step: str
    context_levels: list[str]
    budgets: list[str]


class TdbbBudget(StrictModel):
    budget: str
    label: str
    metric: str
    metric_label: str
    context: str
    context_label: str
    x_m3s: float | None = None
    y_m3s: float | None = None


class TdbbPeriodSummary(StrictModel):
    period: Literal["before", "after"]
    run_ids: list[str]
    lot_count: int = Field(ge=0)
    wafer_count: int = Field(ge=0)
    budgets: list[TdbbBudget]


class TdbbBudgetDelta(StrictModel):
    budget: str
    label: str
    metric: str
    metric_label: str
    context: str
    context_label: str
    before_x: float | None = None
    after_x: float | None = None
    delta_x: float | None = None
    delta_x_pct: float | None = None
    before_y: float | None = None
    after_y: float | None = None
    delta_y: float | None = None
    delta_y_pct: float | None = None


class TdbbLargestIncrease(StrictModel):
    budget: str
    label: str
    axis: Literal["X", "Y"]
    delta: float
    delta_pct: float


class TdbbCompareResult(StrictModel):
    before: TdbbPeriodSummary
    after: TdbbPeriodSummary
    budgets: list[TdbbBudgetDelta]
    largest_increase: TdbbLargestIncrease | None = None
    headline: str


class TdbbPeriod(StrictModel):
    period: Literal["before", "after"]
    start_date: str
    end_date: str
    run_ids: list[str]
    lot_count: int = Field(ge=0)
    wafer_count: int = Field(ge=0)
    budgets: list[TdbbBudget]


class TdbbMapPoint(StrictModel):
    x: float
    y: float
    dx: float
    dy: float
    m3s_x: float | None = None
    m3s_y: float | None = None


class TdbbMap(StrictModel):
    budget: str
    period: Literal["before", "after"]
    level: Literal["wafer", "field"]
    points: list[TdbbMapPoint]


class TdbbRunResult(StrictModel):
    status: Literal["COMPLETED"]
    change_date: str
    settings: TdbbSettings
    periods: list[TdbbPeriod]
    maps: list[TdbbMap]


class TdbbWafer(StrictModel):
    wafer_id: str
    chuck_id: str | None = None


class TdbbRunInfo(StrictModel):
    run_id: str
    status: Literal["COMPLETED"]
    model_step: str
    context_levels: list[str]
    product_id: str
    layer_id: str
    exposure_equipment_id: str
    lot_id: str
    lot_start: str
    wafers: list[TdbbWafer]


class TdbbRunData(StrictModel):
    run_id: str
    tables: dict[str, list[dict[str, Any]]]
