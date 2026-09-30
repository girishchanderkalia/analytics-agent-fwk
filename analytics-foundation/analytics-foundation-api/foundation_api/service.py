from __future__ import annotations
from datetime import date,datetime,timedelta
from math import sqrt
from statistics import mean,pstdev
from typing import Any
from uuid import uuid4
from .errors import WorkspaceNotFoundError,RegistrationNotFoundError,TdbbRunNotFoundError
from .models import *
from .tdbb import BUDGETS,TABLES,process_period,run_rows
class FoundationService:
 def __init__(self,repository,trend_table:str,wafer_table:str):
  self.repo=repository;self.trend_table=trend_table;self.wafer_table=wafer_table;self.workspaces={};self.registrations={}
 def ready(self):self.repo.trend_rows();self.repo.wafer_rows()
 def metadata(self):return DatasetMetadata(trend_table=self.trend_table,wafer_table=self.wafer_table)
 def _rows(self,q:TrendQueryRequest):
  start=date.fromisoformat(q.start_date) if q.start_date else (date.today()-timedelta(days=q.days-1) if q.days else date.min)
  end=date.fromisoformat(q.end_date) if q.end_date else date.max
  for row in self.repo.trend_rows():
   machine=str(row.get("machine") or row.get("exposureEquipmentId") or "UNKNOWN_MACHINE")
   product=str(row.get("product") or row.get("productId") or "UNKNOWN_PRODUCT")
   lot=str(row.get("lot_id") or row.get("lotId") or "")
   layer=str(row.get("layer_id") or row.get("layerId") or "")
   chuck=row.get("chuck_id") or row.get("chuckId")
   timestamp=row.get("date") or row.get("lotStart") or row.get("lot_start")
   if timestamp is None:continue
   dt=datetime.fromisoformat(str(timestamp).replace("Z","+00:00"))
   if not start<=dt.date()<=end:continue
   if q.lot_ids and lot not in q.lot_ids:continue
   if q.product_ids and product not in q.product_ids:continue
   if q.layer_ids and layer not in q.layer_ids:continue
   if q.exposure_equipment_ids and machine not in q.exposure_equipment_ids:continue
   if q.chuck_ids and chuck not in q.chuck_ids:continue
   yield row,dt,machine,product,lot,layer,chuck
 def trends(self,q:TrendQueryRequest)->TrendResponse:
  groups={}
  for row,dt,machine,product,lot,layer,chuck in self._rows(q):
   value=row.get("kpi_value",row.get("kpiValue1"))
   if value is None:continue
   value_y=row.get("kpiValue2")
   key=(machine,product,lot or None,layer or None)
   group=groups.setdefault(key,TrendSeries(machine=machine,product=product,lot_id=lot or None,layer_id=layer or None,exposure_equipment_id=machine,points=[]))
   group.points.append(TrendPoint(date=dt.isoformat(),kpi_value=float(value),kpi_value_y=None if value_y is None else float(value_y),lot_id=lot or None,wafer_id=row.get("waferId") or row.get("wafer_id"),chuck_id=chuck))
  for group in groups.values():group.points.sort(key=lambda p:p.date)
  return TrendResponse(series=list(groups.values()))
 def _tdbb_runs(self):return {run["run_id"]:run for run in self.repo.tdbb_runs()}
 def run_tdbb(self,q:TdbbRunRequest)->TdbbRunResult:
  # Mock processing: resolve the request to TDBB runs that already exist in the run index.
  start,end,change=(date.fromisoformat(v) for v in (q.start_date,q.end_date,q.change_date))
  if not start<change<=end:raise ValueError("change_date must fall after start_date and on or before end_date")
  selected={"before":[],"after":[]}
  for run in self._tdbb_runs().values():
   day=datetime.fromisoformat(run["lot_start"]).date()
   if not start<=day<=end:continue
   if q.lot_ids and run["lot_id"] not in q.lot_ids:continue
   if q.product_ids and run["product_id"] not in q.product_ids:continue
   if q.layer_ids and run["layer_id"] not in q.layer_ids:continue
   if q.exposure_equipment_ids and run["exposure_equipment_id"] not in q.exposure_equipment_ids:continue
   if run["model_step"]!=q.model_step or not set(q.context_levels)<=set(run["context_levels"]):continue
   selected["before" if day<change else "after"].append(run)
  bounds={"before":(start,change-timedelta(days=1)),"after":(change,end)}
  periods=[];maps=[]
  for name,runs in selected.items():
   runs.sort(key=lambda run:run["lot_start"])
   processed=process_period(runs,q.chuck_ids)
   periods.append(TdbbPeriod(period=name,start_date=bounds[name][0].isoformat(),end_date=bounds[name][1].isoformat(),run_ids=[run["run_id"] for run in runs],lot_count=processed["lot_count"],wafer_count=processed["wafer_count"],budgets=[TdbbBudget(**b) for b in processed["budgets"]]))
   maps.extend(TdbbMap(budget=budget,period=name,level=level,points=[TdbbMapPoint(**p) for p in points]) for budget,levels in processed["maps"].items() for level,points in levels.items())
  return TdbbRunResult(status="COMPLETED",change_date=q.change_date,settings=TdbbSettings(model_step=q.model_step,context_levels=list(q.context_levels),budgets=list(BUDGETS)),periods=periods,maps=maps)
 def _tdbb_run(self,run_id):
  try:return self._tdbb_runs()[run_id]
  except KeyError as exc:raise TdbbRunNotFoundError(run_id) from exc
 def tdbb_run(self,run_id)->TdbbRunInfo:return TdbbRunInfo(**self._tdbb_run(run_id))
 def tdbb_data(self,run_id,tables:list[str]|None=None)->TdbbRunData:
  unknown=set(tables or ())-set(TABLES)
  if unknown:raise ValueError(f"Unknown TDBB tables: {sorted(unknown)}")
  return TdbbRunData(run_id=run_id,tables=run_rows(self._tdbb_run(run_id),tables or TABLES))
 def distribution(self,q):
  values=[p.kpi_value for s in self.trends(q).series for p in s.points]
  if not values:return DistributionStats(sample_count=0)
  ordered=sorted(values)
  def percentile(f):return ordered[min(len(ordered)-1,max(0,int(round((len(ordered)-1)*f))))]
  avg=mean(values);sd=pstdev(values) if len(values)>1 else 0.0
  return DistributionStats(sample_count=len(values),p95=percentile(.95),p99=percentile(.99),mean=avg,stdev=sd,bell_curve_range=BellCurveRange(lower=avg-3*sd,upper=avg+3*sd))
 def create_workspace(self):
  wid=f"workspace-{uuid4()}";self.workspaces[wid]={"filters":{},"connection":{"workspace_id":wid}};return WorkspaceResponse(workspace_id=wid)
 def _workspace(self,wid):
  if wid not in self.workspaces:raise WorkspaceNotFoundError(wid)
  return self.workspaces[wid]
 def add_filters(self,wid,filters):self._workspace(wid)["filters"]=dict(filters);return WorkspaceFiltersResponse(workspace_id=wid,filters=dict(filters))
 def connection_info(self,wid):return WorkspaceConnectionInfo(workspace_id=wid,values=dict(self._workspace(wid)["connection"]))
 def register(self,wid,request):
  self._workspace(wid);rid=f"registration-{uuid4()}";status=RegistrationStatus(registration_id=rid,workspace_id=wid,status="READY",progress_pct=100,table=request.table);self.registrations[(wid,rid)]=status;return status
 def registration(self,wid,rid):
  try:return self.registrations[(wid,rid)]
  except KeyError as exc:raise RegistrationNotFoundError(rid) from exc
 def wafers(self,request):
  if request.workspace_id!="TREND_PREVIEW":self._workspace(request.workspace_id)
  rows=[]
  for raw in self.repo.wafer_rows():
   row=_identified_wafer_row(raw)
   if any(str(row.get(k,""))!=str(v) for k,v in request.filters.items() if v is not None):continue
   x=float(row.get("overlay_x_um",row.get("overlay_x",0)) or 0);y=float(row.get("overlay_y_um",row.get("overlay_y",0)) or 0);row.setdefault("overlay_magnitude_um",round(sqrt(x*x+y*y),4));rows.append(row)
  anomalous=list(dict.fromkeys(str(r.get("wafer_id")) for r in rows if r.get("wafer_id") and float(r.get("overlay_magnitude_um",0))>.20))
  return WaferQueryResponse(workspace_id=request.workspace_id,table=request.table,rows=rows,anomalous_wafers=anomalous)

# Wafer source columns are fully qualified; expose the identity the contract names.
_WAFER_IDENTITY={
 "wafer_id":("wafer_id","waferId","exposureprocessjob_waferexposureprocessjob_waferid"),
 "lot_id":("lot_id","lotId","exposureprocessjob_lotid"),
 "layer_id":("layer_id","layerId","measureprocessjob_layerid"),
 "exposure_equipment_id":("exposure_equipment_id","exposureEquipmentId","machine","exposureprocessjob_equipment_equipmentid"),
}

def _identified_wafer_row(raw:dict)->dict:
 row=dict(raw)
 for name,candidates in _WAFER_IDENTITY.items():
  if row.get(name) is not None:continue
  for candidate in candidates:
   value=raw.get(candidate)
   if value is not None:row[name]=value;break
 return row
