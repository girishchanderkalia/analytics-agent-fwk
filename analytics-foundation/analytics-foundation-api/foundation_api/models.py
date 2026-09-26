from typing import Any
from pydantic import BaseModel, ConfigDict, Field
class StrictModel(BaseModel): model_config=ConfigDict(extra="forbid")
class HealthResponse(StrictModel): status:str="ok"
class DatasetMetadata(BaseModel): trend_table:str;wafer_table:str
class TrendQueryRequest(StrictModel):
    days:int|None=Field(default=None,ge=1,le=90);start_date:str|None=None;end_date:str|None=None
    lot_ids:list[str]=Field(default_factory=list);product_ids:list[str]=Field(default_factory=list)
    layer_ids:list[str]=Field(default_factory=list);exposure_equipment_ids:list[str]=Field(default_factory=list)
class TrendPoint(StrictModel): date:str;kpi_value:float;lot_id:str|None=None
class TrendSeries(StrictModel):
    machine:str;product:str;lot_id:str|None=None;layer_id:str|None=None;exposure_equipment_id:str|None=None;points:list[TrendPoint]
class TrendResponse(StrictModel): series:list[TrendSeries]
class BellCurveRange(StrictModel): lower:float;upper:float
class DistributionStats(StrictModel):
    sample_count:int=Field(ge=0);p95:float|None=None;p99:float|None=None;mean:float|None=None;stdev:float|None=None;bell_curve_range:BellCurveRange|None=None
class WorkspaceResponse(StrictModel): workspace_id:str
class WorkspaceFiltersRequest(StrictModel): filters:dict[str,Any]
class WorkspaceFiltersResponse(StrictModel): workspace_id:str;filters:dict[str,Any]
class WorkspaceConnectionInfo(StrictModel): workspace_id:str;values:dict[str,Any]
class RegistrationRequest(StrictModel): dataset:str;table:str
class RegistrationStatus(StrictModel):
    registration_id:str;workspace_id:str;status:str;progress_pct:int=Field(ge=0,le=100);table:str;error:str|None=None
class WaferQueryRequest(StrictModel): workspace_id:str;table:str;filters:dict[str,Any]=Field(default_factory=dict)
class WaferQueryResponse(StrictModel): workspace_id:str;table:str;rows:list[dict[str,Any]];anomalous_wafers:list[str]
