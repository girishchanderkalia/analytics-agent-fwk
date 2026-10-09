from datetime import datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WaferLevelKpiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lotExposureStartFrom: datetime
    lotExposureStartTo: datetime | None = None
    productIds: list[str | None] = Field(default_factory=list)
    layerIds: list[str | None] = Field(default_factory=list)
    exposureEquipmentIds: list[str | None] = Field(default_factory=list)
    lotIds: list[str | None] = Field(default_factory=list)
    chuckIds: list[str | None] = Field(default_factory=list)

    @field_validator("lotExposureStartFrom", "lotExposureStartTo", mode="before")
    @classmethod
    def parse_bound(cls, value: Any, info: Any) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Expected an ISO date or date-time with offset")
        text = value.strip()
        if len(text) == 10:
            day = datetime.strptime(text, "%Y-%m-%d").date()
            bound = time.max if info.field_name == "lotExposureStartTo" else time.min
            return datetime.combine(day, bound, timezone.utc)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Date-time must include an offset")
        return parsed

    @field_validator("productIds", "layerIds", "exposureEquipmentIds", "lotIds", "chuckIds", mode="before")
    @classmethod
    def empty_ids(cls, value: Any) -> Any:
        return [] if value is None else value

    @model_validator(mode="after")
    def ordered_window(self) -> "WaferLevelKpiRequest":
        if self.lotExposureStartTo is not None and self.lotExposureStartFrom > self.lotExposureStartTo:
            raise ValueError("lotExposureStartFrom must not be after lotExposureStartTo")
        return self


class WaferLevelKpi(BaseModel):
    model_config = ConfigDict(extra="forbid")

    productId: str | None
    lotId: str | None
    layerId: str | None
    waferId: str | None
    chuckId: str | None
    measureProcessJobId: float | None
    exposureEquipmentId: str | None
    measurementEquipmentId: str | None
    lotStart: datetime
    kpiValue1: float
    kpiValue2: float
    needsIngestion: bool


class WaferLevelKpiResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[WaferLevelKpi]
    rowCount: int = Field(ge=0)
    truncated: bool


def mock_wafer_kpis(series: list[Any], request: WaferLevelKpiRequest, max_rows: int) -> dict[str, Any]:
    rows = []
    for group in series:
        for point in group.points:
            if point.kpi_value_y is None:
                continue
            timestamp = datetime.fromisoformat(point.date.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            if timestamp < request.lotExposureStartFrom:
                continue
            if request.lotExposureStartTo is not None and timestamp > request.lotExposureStartTo:
                continue
            values = (group.product, group.layer_id, group.exposure_equipment_id or group.machine,
                      point.lot_id or group.lot_id, point.chuck_id)
            filters = (request.productIds, request.layerIds, request.exposureEquipmentIds,
                       request.lotIds, request.chuckIds)
            if any(selected and value not in selected for value, selected in zip(values, filters)):
                continue
            rows.append({
                "productId": values[0], "lotId": values[3], "layerId": values[1],
                "waferId": point.wafer_id, "chuckId": point.chuck_id,
                "measureProcessJobId": point.measure_process_job_id,
                "exposureEquipmentId": values[2], "measurementEquipmentId": point.measurement_equipment_id,
                "lotStart": timestamp.isoformat().replace("+00:00", "Z"),
                "kpiValue1": float(Decimal(str(point.kpi_value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "kpiValue2": float(Decimal(str(point.kpi_value_y)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "needsIngestion": point.needs_ingestion,
            })
    rows.sort(key=lambda row: (row["measureProcessJobId"] is None, row["measureProcessJobId"] or 0,
                               row["waferId"] or ""))
    return {"rows": rows[:max_rows], "rowCount": min(len(rows), max_rows), "truncated": len(rows) > max_rows}