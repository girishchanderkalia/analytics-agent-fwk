from collections import defaultdict
from datetime import date, datetime
from typing import Literal

from pydantic import Field, model_validator

from .models import StrictModel


METRIC_COLUMNS = {
    "MAX": "measured_raw_max",
    "MIN": "measured_raw_min",
    "MEAN": "measured_raw_mean",
    "M3S": "measured_raw_m3s",
    "MAX_997": "filtered_raw_99_7",
}


class OverlayQueryRequest(StrictModel):
    kpi: Literal["MEASURED_OVERLAY"] = "MEASURED_OVERLAY"
    metric: Literal["MAX", "MIN", "MEAN", "M3S", "MAX_997"] = "MEAN"
    start_date: date | None = None
    end_date: date | None = None
    lot_ids: list[str] = Field(default_factory=list)
    product_ids: list[str] = Field(default_factory=list)
    excluded_product_ids: list[str] = Field(default_factory=list)
    layer_ids: list[str] = Field(default_factory=list)
    exposure_equipment_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class OverlayPoint(StrictModel):
    lot_step_id: int
    lot_metrology_step_id: int
    product_id: str | None = None
    lot_id: str | None = None
    layer_id: str | None = None
    exposure_machine_id: str | None = None
    exposure_equipment_id: str | None = None
    metrology_equipment_id: str | None = None
    lot_start: datetime | None = None
    lot_end: datetime | None = None
    kpi_x: float | None = None
    kpi_y: float | None = None
    needs_ingestion: bool = False


class OverlayResponse(StrictModel):
    kpi: str
    metric: str
    points: list[OverlayPoint]


def query_overlay(repository, query: OverlayQueryRequest) -> OverlayResponse:
    exposures = defaultdict(list)
    metrologies = defaultdict(list)
    mappings = defaultdict(list)
    for row in repository.table_rows("lot_exposure_step"):
        exposures[row["lot_step_id"]].append(row)
    for row in repository.table_rows("lot_metrology_step"):
        metrologies[row["lot_step_id"]].append(row)
    for row in repository.table_rows("lot_kpi_mapping"):
        if row.get("aggregation_level") == "LOT" and row.get("lot_metrology_step_id") is not None:
            mappings[row["lot_metrology_step_id"]].append(row)
    kpis = {row["id"]: row for row in repository.table_rows("lot_metrology_overlay_kpis")}
    machines = {row["id"]: row for row in repository.table_rows("exposure_machine")}
    prefix = METRIC_COLUMNS[query.metric]
    points = []
    seen = set()
    for lot in sorted(repository.table_rows("lot_step"), key=lambda row: row["id"]):
        for metrology in metrologies[lot["id"]]:
            for mapping in mappings[metrology["id"]]:
                values = kpis.get(mapping["id"])
                if values is None:
                    continue
                for exposure in exposures[lot["id"]] or [{}]:
                    machine_id = exposure.get("machine_id")
                    machine = machines.get(machine_id, {})
                    point = OverlayPoint(
                        lot_step_id=lot["id"],
                        lot_metrology_step_id=metrology["id"],
                        product_id=exposure.get("product_id"),
                        lot_id=exposure.get("key_lot_id"),
                        layer_id=exposure.get("key_layer_id"),
                        exposure_machine_id=machine_id,
                        exposure_equipment_id=machine.get("customername") or machine_id,
                        metrology_equipment_id=metrology.get("machine_id"),
                        lot_start=datetime.fromisoformat(exposure["lot_start"]) if exposure.get("lot_start") else None,
                        lot_end=datetime.fromisoformat(exposure["lot_end"]) if exposure.get("lot_end") else None,
                        kpi_x=values.get(prefix + "_x"),
                        kpi_y=values.get(prefix + "_y"),
                    )
                    if query.start_date and (point.lot_start is None or point.lot_start.date() < query.start_date):
                        continue
                    if query.end_date and (point.lot_start is None or point.lot_start.date() > query.end_date):
                        continue
                    if any(selected and value not in selected for selected, value in (
                        (query.lot_ids, point.lot_id),
                        (query.product_ids, point.product_id),
                        (query.layer_ids, point.layer_id),
                        (query.exposure_equipment_ids, point.exposure_equipment_id),
                    )):
                        continue
                    if point.product_id in query.excluded_product_ids:
                        continue
                    key = tuple(point.model_dump().values())
                    if key not in seen:
                        seen.add(key)
                        points.append(point)
    return OverlayResponse(kpi=query.kpi, metric=query.metric, points=points)