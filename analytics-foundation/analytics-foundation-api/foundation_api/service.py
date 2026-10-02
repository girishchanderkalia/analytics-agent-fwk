from __future__ import annotations
from datetime import date,datetime,timedelta
from math import sqrt
from random import Random
from statistics import mean,pstdev
from typing import Any
from uuid import uuid4
from .errors import WorkspaceNotFoundError,RegistrationNotFoundError,TdbbRunNotFoundError
from .models import *
from .tdbb import BUDGETS,TABLES,process_period,run_rows
class FoundationService:
 def __init__(self,repository,trend_table:str,wafer_table:str):
  self.repo=repository;self.trend_table=trend_table;self.wafer_table=wafer_table;self.workspaces={};self.registrations={};self._wafer_template_cache=None
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
 def compare_tdbb_runs(self,q:TdbbCompareRequest)->TdbbCompareResult:
  runs=self._tdbb_runs()
  try:
   before_runs=[runs[run_id] for run_id in q.before_run_ids];after_runs=[runs[run_id] for run_id in q.after_run_ids]
  except KeyError as exc:raise TdbbRunNotFoundError(str(exc.args[0])) from exc
  summaries=[]
  for period,selected in (("before",before_runs),("after",after_runs)):
   processed=process_period(selected)
   summaries.append(TdbbPeriodSummary(period=period,run_ids=[run["run_id"] for run in selected],lot_count=processed["lot_count"],wafer_count=processed["wafer_count"],budgets=[TdbbBudget(**budget) for budget in processed["budgets"]]))
  before,after=summaries;before_budgets={budget.budget:budget for budget in before.budgets};deltas=[];increases=[]
  for budget in after.budgets:
   previous=before_budgets.get(budget.budget);delta_values={}
   for axis in ("x","y"):
    old=getattr(previous,f"{axis}_m3s",None) if previous else None;new=getattr(budget,f"{axis}_m3s")
    delta=None if old is None or new is None else round(new-old,3);percentage=None if old in (None,0) or new is None else round((new-old)/old*100,1)
    delta_values.update({f"before_{axis}":old,f"after_{axis}":new,f"delta_{axis}":delta,f"delta_{axis}_pct":percentage})
    if delta is not None and percentage is not None and delta>0:increases.append((percentage,TdbbLargestIncrease(budget=budget.budget,label=budget.label,axis=axis.upper(),delta=delta,delta_pct=percentage)))
   deltas.append(TdbbBudgetDelta(budget=budget.budget,label=budget.label,metric=budget.metric,metric_label=budget.metric_label,context=budget.context,context_label=budget.context_label,**delta_values))
  largest=max(increases,key=lambda item:item[0],default=(None,None))[1]
  headline="No TDBB budget increased after the change date." if largest is None else f"Largest increase: {largest.label} {largest.axis} +{largest.delta_pct}% ({largest.delta} nm delta)"
  return TdbbCompareResult(before=before,after=after,budgets=deltas,largest_increase=largest,headline=headline)
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
 def detect_outliers(self,q:OutlierDetectionRequest)->OutlierDetectionResult:
  # Exhaustive, deterministic threshold check over every point in every series; no sampling.
  # A threshold must mark every violating point; whether a candidate's machine
  # also has wafer-level data is handled later, when investigating that candidate.
  outliers=[]
  for series in self.trends(q).series:
   values=sorted(p.kpi_value for p in series.points)
   if not values:continue
   middle=len(values)//2
   baseline=values[middle] if len(values)%2 else (values[middle-1]+values[middle])/2
   if q.mode=="absolute":
    applied=baseline*(1+(q.limit_value if q.direction=="above" else -q.limit_value)/100) if q.threshold_unit=="percent" else q.limit_value
   else:
    applied=baseline*(1+(q.baseline_deviation_pct if q.baseline_deviation_pct is not None else 3.0)/100)
   above=q.mode=="baseline" or q.direction=="above"
   for point in series.points:
    if (point.kpi_value>=applied) if above else (point.kpi_value<=applied):
     outliers.append(OutlierPoint(machine=series.machine,product=series.product,lot_id=series.lot_id,layer_id=series.layer_id,exposure_equipment_id=series.exposure_equipment_id,date=point.date,kpi_value=point.kpi_value,kpi_value_y=point.kpi_value_y,baseline=baseline,applied_threshold=applied))
  return OutlierDetectionResult(outliers=outliers)
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
  # A lot with trend data but no measured wafer rows still gets an investigable wafer map.
  if not rows and request.filters.get("lot_id"):rows=self._synthesize_wafer_rows(request.filters)
  anomalous=list(dict.fromkeys(str(r.get("wafer_id")) for r in rows if r.get("wafer_id") and float(r.get("overlay_magnitude_um",0))>.20))
  return WaferQueryResponse(workspace_id=request.workspace_id,table=request.table,rows=rows,anomalous_wafers=anomalous)
 def _wafer_template(self):
  # Reuse the real tool's field/intrafield grid so synthesized wafers have a plausible layout.
  if self._wafer_template_cache is None:
   rows=self.repo.wafer_rows()
   first=(rows[0]["exposureprocessjob_lotid"],rows[0]["exposureprocessjob_waferexposureprocessjob_waferid"])
   keys=("exposureprocessjob_waferexposureprocessjob_exposurelogicalwafer_exposedfield_field_center_x","exposureprocessjob_waferexposureprocessjob_exposurelogicalwafer_exposedfield_field_center_y","measureprocessjob_wafermeasureprocessjob_measurement_intrafieldposition_position_x","measureprocessjob_wafermeasureprocessjob_measurement_intrafieldposition_position_y","exposureprocessjob_reticle_image_imagesize_width","exposureprocessjob_reticle_image_imagesize_height")
   self._wafer_template_cache=[{k:r[k] for k in keys} for r in rows if (r["exposureprocessjob_lotid"],r["exposureprocessjob_waferexposureprocessjob_waferid"])==first]
  return self._wafer_template_cache
 def _synthesize_wafer_rows(self,filters):
  lot_id=filters.get("lot_id")
  trend_row=next((row for row in self.repo.trend_rows() if str(row.get("lot_id") or row.get("lotId"))==str(lot_id)),None)
  if trend_row is None:return []
  machine=filters.get("exposure_equipment_id") or str(trend_row.get("machine") or trend_row.get("exposureEquipmentId") or "")
  layer_id=filters.get("layer_id") or str(trend_row.get("layer_id") or trend_row.get("layerId") or "")
  kpi_value=float(trend_row.get("kpi_value",trend_row.get("kpiValue1")) or 3.0)
  spread=max(0.15,(kpi_value-2.5)*0.6)
  rows=[]
  for index in range(1,5):
   wafer_id=f"wafer{index}";chuck_id="Waferstage chuck ID 1" if index%2 else "Waferstage chuck ID 2"
   rng=Random(f"synthetic|{lot_id}|{wafer_id}")
   for point in self._wafer_template():
    overlay_x=round(rng.gauss(0,spread),3);overlay_y=round(rng.gauss(0,spread),3)
    row=_identified_wafer_row({**point,"overlay_x":overlay_x,"overlay_y":overlay_y,"overlay_valid_x":1,"overlay_valid_y":1,
     "exposureprocessjob_lotid":lot_id,"exposureprocessjob_waferexposureprocessjob_waferid":wafer_id,
     "exposureprocessjob_waferexposureprocessjob_chuck_id":chuck_id,"measureprocessjob_layerid":layer_id,
     "exposureprocessjob_equipment_equipmentid":machine})
    row["overlay_magnitude_um"]=round(sqrt(overlay_x*overlay_x+overlay_y*overlay_y),4)
    rows.append(row)
  return rows

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
