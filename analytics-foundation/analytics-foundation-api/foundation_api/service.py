from __future__ import annotations
from datetime import date,datetime,timedelta
from math import sqrt
from statistics import mean,pstdev
from typing import Any
from uuid import uuid4
from .errors import WorkspaceNotFoundError,RegistrationNotFoundError
from .models import *
class FoundationService:
 def __init__(self,repository,trend_table:str,wafer_table:str):
  self.repo=repository;self.trend_table=trend_table;self.wafer_table=wafer_table;self.workspaces={};self.registrations={}
 def ready(self):self.repo.trend_rows();self.repo.wafer_rows()
 def metadata(self):return DatasetMetadata(trend_table=self.trend_table,wafer_table=self.wafer_table)
 def trends(self,q:TrendQueryRequest)->TrendResponse:
  start=date.fromisoformat(q.start_date) if q.start_date else (date.today()-timedelta(days=q.days-1) if q.days else date.min)
  end=date.fromisoformat(q.end_date) if q.end_date else date.max
  groups={}
  for row in self.repo.trend_rows():
   machine=str(row.get("machine") or row.get("exposureEquipmentId") or "UNKNOWN_MACHINE")
   product=str(row.get("product") or row.get("productId") or "UNKNOWN_PRODUCT")
   lot=str(row.get("lot_id") or row.get("lotId") or "")
   layer=str(row.get("layer_id") or row.get("layerId") or "")
   timestamp=row.get("date") or row.get("lotStart") or row.get("lot_start")
   value=row.get("kpi_value",row.get("kpiValue1"))
   if timestamp is None or value is None:continue
   dt=datetime.fromisoformat(str(timestamp).replace("Z","+00:00"))
   if not start<=dt.date()<=end:continue
   if q.lot_ids and lot not in q.lot_ids:continue
   if q.product_ids and product not in q.product_ids:continue
   if q.layer_ids and layer not in q.layer_ids:continue
   if q.exposure_equipment_ids and machine not in q.exposure_equipment_ids:continue
   key=(machine,product,lot or None,layer or None)
   group=groups.setdefault(key,TrendSeries(machine=machine,product=product,lot_id=lot or None,layer_id=layer or None,exposure_equipment_id=machine,points=[]))
   group.points.append(TrendPoint(date=dt.isoformat(),kpi_value=float(value),lot_id=lot or None))
  for group in groups.values():group.points.sort(key=lambda p:p.date)
  return TrendResponse(series=list(groups.values()))
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
   if any(str(raw.get(k,""))!=str(v) for k,v in request.filters.items() if v is not None):continue
   row=dict(raw);x=float(row.get("overlay_x_um",row.get("overlay_x",0)) or 0);y=float(row.get("overlay_y_um",row.get("overlay_y",0)) or 0);row.setdefault("overlay_magnitude_um",round(sqrt(x*x+y*y),4));rows.append(row)
  anomalous=list(dict.fromkeys(str(r.get("wafer_id")) for r in rows if r.get("wafer_id") and float(r.get("overlay_magnitude_um",0))>.20))
  return WaferQueryResponse(workspace_id=request.workspace_id,table=request.table,rows=rows,anomalous_wafers=anomalous)
