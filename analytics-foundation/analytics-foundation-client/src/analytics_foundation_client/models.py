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
    trend_table: str = Field(description="Name of the published trend dataset table.")
    wafer_table: str = Field(description="Name of the published wafer dataset table.")


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
    date: str = Field(description="ISO date of the observation.")
    kpi_value: float = Field(description="Overlay X KPI, |mean| + 3 sigma in nm.")
    kpi_value_y: float | None = Field(default=None, description="Overlay Y KPI, |mean| + 3 sigma in nm.")
    lot_id: str | None = None
    wafer_id: str | None = None
    chuck_id: str | None = Field(default=None, description="Wafer stage chuck identifier.")
    measure_process_job_id: float | None = None
    measurement_equipment_id: str | None = None
    needs_ingestion: bool = False


class TrendSeries(StrictModel):
    machine: str = Field(description="Exposure equipment (scanner) identifier.")
    product: str
    lot_id: str | None = None
    layer_id: str | None = None
    exposure_equipment_id: str | None = None
    points: list[TrendPoint] = Field(description="Per-wafer KPI observations ordered by date.")


class TrendResponse(StrictModel):
    series: list[TrendSeries] = Field(description="Trend series grouped by machine, product, lot and layer.")


class BellCurveRange(StrictModel):
    lower: float = Field(description="Lower bound of the empirical bell-curve range.")
    upper: float = Field(description="Upper bound of the empirical bell-curve range.")


class DistributionStats(StrictModel):
    sample_count: int = Field(ge=0, description="Number of KPI samples the statistics are computed from.")
    p95: float | None = Field(default=None, description="95th percentile KPI value.")
    p99: float | None = Field(default=None, description="99th percentile KPI value.")
    mean: float | None = Field(default=None, description="Mean KPI value.")
    stdev: float | None = Field(default=None, description="KPI standard deviation.")
    bell_curve_range: BellCurveRange | None = Field(
        default=None, description="Empirical normal-range bounds derived from the distribution."
    )


class OutlierDetectionRequest(TrendQueryRequest):
    mode: Literal["absolute", "baseline"] = "baseline"
    limit_value: float = 3.0
    direction: Literal["above", "below"] = "above"
    threshold_unit: Literal["percent", "absolute"] = "percent"
    baseline_deviation_pct: float | None = None


class OutlierPoint(StrictModel):
    machine: str
    product: str
    lot_id: str | None = None
    layer_id: str | None = None
    exposure_equipment_id: str | None = None
    date: str = Field(description="ISO date of the outlier observation.")
    kpi_value: float = Field(description="Overlay X KPI value that violated the threshold, |mean| + 3 sigma in nm.")
    kpi_value_y: float | None = Field(default=None, description="Overlay Y KPI value, |mean| + 3 sigma in nm.")
    baseline: float = Field(description="Per-series baseline KPI value the point was compared against.")
    applied_threshold: float = Field(description="Absolute or percentage threshold applied to flag this point.")


class OutlierDetectionResult(StrictModel):
    outliers: list[OutlierPoint] = Field(
        description="Every trend point violating the absolute or baseline threshold."
    )


class WorkspaceResponse(StrictModel):
    workspace_id: str = Field(description="Identifier of the created governed analytical workspace.")


class WorkspaceFiltersRequest(StrictModel):
    filters: dict[str, Any]


class WorkspaceFiltersResponse(StrictModel):
    workspace_id: str
    filters: dict[str, Any] = Field(description="Filters now applied to the workspace.")


class WorkspaceConnectionInfo(StrictModel):
    workspace_id: str
    values: dict[str, Any] = Field(
        description="Governed connection details for querying the workspace directly."
    )


class RegistrationRequest(StrictModel):
    dataset: str
    table: str


class RegistrationStatus(StrictModel):
    registration_id: str
    workspace_id: str
    status: Literal["PENDING", "RUNNING", "READY", "FAILED"] = Field(
        description="Dataset registration lifecycle state; data is queryable only once READY."
    )
    progress_pct: int = Field(ge=0, le=100, description="Registration completion percentage.")
    table: str = Field(description="Registered table name available for query once READY.")
    error: str | None = Field(default=None, description="Failure reason when status is FAILED.")


class WaferQueryRequest(StrictModel):
    workspace_id: str
    table: str
    filters: dict[str, Any] = Field(default_factory=dict)


class WaferQueryResponse(StrictModel):
    workspace_id: str
    table: str
    rows: list[dict[str, Any]] = Field(description="Wafer-level rows from the registered table.")
    anomalous_wafers: list[str] = Field(
        description="Wafer identifiers flagged as anomalous among the returned rows."
    )


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
    model_step: str = Field(description="TDBB model step applied, e.g. 10par.")
    context_levels: list[str] = Field(description="Context levels computed, e.g. AVG (lot) and W2W (wafer).")
    budgets: list[str] = Field(description="Budget identifiers included in this run's overview.")


class TdbbBudget(StrictModel):
    budget: str = Field(description="Budget identifier, e.g. nce_wafer.average.")
    label: str = Field(description="Human-readable budget label, e.g. 'NCE - Wafer · Average'.")
    metric: str = Field(
        description="Metric component of the budget: nce_wafer, nce_field, ce_wafer, ce_field or ce_translation."
    )
    metric_label: str = Field(description="Human-readable metric label, e.g. 'NCE - Wafer'.")
    context: str = Field(description="Context level of the budget: average, c2c, l2l or w2w.")
    context_label: str = Field(description="Human-readable context label, e.g. 'Wafer to wafer'.")
    x_m3s: float | None = Field(default=None, description="Overlay X budget value, |mean| + 3 sigma in nm.")
    y_m3s: float | None = Field(default=None, description="Overlay Y budget value, |mean| + 3 sigma in nm.")
    mean_x: float | None = Field(default=None, description="Overlay X component mean, nm; combine across components by direct sum.")
    mean_y: float | None = Field(default=None, description="Overlay Y component mean, nm; combine across components by direct sum.")
    sigma_x: float | None = Field(default=None, description="Overlay X component sigma, nm; combine across components in quadrature (RSS).")
    sigma_y: float | None = Field(default=None, description="Overlay Y component sigma, nm; combine across components in quadrature (RSS).")


class TdbbPeriodSummary(StrictModel):
    period: Literal["before", "after"] = Field(
        description="Which side of the change date this summary covers."
    )
    run_ids: list[str] = Field(description="TDBB run identifiers contributing to this period.")
    lot_count: int = Field(ge=0, description="Number of lots included in this period.")
    wafer_count: int = Field(ge=0, description="Number of wafers included in this period.")
    budgets: list[TdbbBudget] = Field(
        description="Budget overview for this period, one entry per metric/context cell."
    )


class TdbbBudgetDelta(StrictModel):
    budget: str
    label: str
    metric: str
    metric_label: str
    context: str
    context_label: str
    before_x: float | None = Field(default=None, description="Overlay X budget before the change, in nm.")
    after_x: float | None = Field(default=None, description="Overlay X budget after the change, in nm.")
    delta_x: float | None = Field(default=None, description="Overlay X budget change (after - before), in nm.")
    delta_x_pct: float | None = Field(default=None, description="Overlay X budget relative change, in percent.")
    before_y: float | None = Field(default=None, description="Overlay Y budget before the change, in nm.")
    after_y: float | None = Field(default=None, description="Overlay Y budget after the change, in nm.")
    delta_y: float | None = Field(default=None, description="Overlay Y budget change (after - before), in nm.")
    delta_y_pct: float | None = Field(default=None, description="Overlay Y budget relative change, in percent.")


class TdbbLargestIncrease(StrictModel):
    budget: str
    label: str
    axis: Literal["X", "Y"] = Field(description="Overlay axis with the largest relative budget increase.")
    delta: float = Field(description="Largest budget increase, in nm.")
    delta_pct: float = Field(description="Largest budget increase, in percent.")


class TdbbCompareResult(StrictModel):
    before: TdbbPeriodSummary
    after: TdbbPeriodSummary
    budgets: list[TdbbBudgetDelta] = Field(description="Before/after delta for every TDBB budget cell.")
    largest_increase: TdbbLargestIncrease | None = Field(
        default=None, description="Budget and axis with the largest relative increase, or null if none increased."
    )
    headline: str = Field(description="One-line summary of the largest budget increase.")


class TdbbPeriod(StrictModel):
    period: Literal["before", "after"] = Field(description="Which side of the change date this period covers.")
    start_date: str
    end_date: str
    run_ids: list[str]
    lot_count: int = Field(ge=0)
    wafer_count: int = Field(ge=0)
    budgets: list[TdbbBudget] = Field(
        description="Budget overview for this period, one entry per metric/context cell."
    )
    radial_profile: dict[str, list[dict[str, Any]]] = Field(
        default_factory=dict,
        description=(
            "Center-vs-edge wafer-radius bands (nm, |mean|+3sigma) for the wafer-level "
            "metrics (ce_wafer, nce_wafer) at the average context, keyed by '<metric>.average'. "
            "Used only for NCE root-cause analysis, not the TDBB overview."
        ),
    )


class TdbbMapPoint(StrictModel):
    x: float = Field(description="Field or wafer X position.")
    y: float = Field(description="Field or wafer Y position.")
    dx: float = Field(description="Overlay X residual at this position, in nm.")
    dy: float = Field(description="Overlay Y residual at this position, in nm.")
    m3s_x: float | None = Field(default=None, description="Overlay X |mean| + 3 sigma at this position, in nm.")
    m3s_y: float | None = Field(default=None, description="Overlay Y |mean| + 3 sigma at this position, in nm.")


class TdbbMap(StrictModel):
    budget: str = Field(description="Budget identifier this map visualizes.")
    period: Literal["before", "after"]
    level: Literal["wafer", "field"] = Field(
        description="Spatial granularity of the points: per-wafer or per-field."
    )
    points: list[TdbbMapPoint]


class TdbbRunResult(StrictModel):
    status: Literal["COMPLETED"]
    change_date: str = Field(description="ISO date separating the before and after periods.")
    settings: TdbbSettings
    periods: list[TdbbPeriod] = Field(description="Before and after period summaries.")
    maps: list[TdbbMap] = Field(description="Per-wafer/per-field residual maps backing the budgets.")


class TdbbWafer(StrictModel):
    wafer_id: str
    chuck_id: str | None = Field(default=None, description="Wafer stage chuck identifier.")


class TdbbRunInfo(StrictModel):
    run_id: str
    status: Literal["COMPLETED"]
    model_step: str = Field(description="TDBB model step applied, e.g. 10par.")
    context_levels: list[str] = Field(description="Context levels computed, e.g. AVG (lot) and W2W (wafer).")
    product_id: str
    layer_id: str
    exposure_equipment_id: str
    lot_id: str
    lot_start: str = Field(description="ISO date the lot started processing.")
    wafers: list[TdbbWafer] = Field(description="Wafers included in this run.")


class TdbbRunData(StrictModel):
    run_id: str
    tables: dict[str, list[dict[str, Any]]] = Field(
        description="Raw TDBB output rows keyed by table name (ce_wafer, ce_field, nce_wafer, nce_field)."
    )
