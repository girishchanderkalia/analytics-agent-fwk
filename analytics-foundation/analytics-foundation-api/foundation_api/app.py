from fastapi import Depends,FastAPI,HTTPException
from functools import lru_cache
from .errors import FoundationServiceError,WorkspaceNotFoundError,RegistrationNotFoundError
from .models import *
from .repositories.json_repository import JsonFoundationRepository
from .service import FoundationService
from .settings import get_settings
app=FastAPI(title="Analytics Foundation API",version="1.0.0")
@lru_cache
def service():
 s=get_settings();return FoundationService(JsonFoundationRepository(s.data_dir),s.trend_table,s.wafer_table)
def dep():return service()
@app.get("/health",response_model=HealthResponse)
def health():return HealthResponse()
@app.get("/ready",response_model=HealthResponse)
def ready(s=Depends(dep)):
 try:s.ready();return HealthResponse()
 except FoundationServiceError as exc:raise HTTPException(503,str(exc)) from exc
@app.get("/metadata",response_model=DatasetMetadata)
def metadata(s=Depends(dep)):return s.metadata()
@app.get("/trends",response_model=TrendResponse)
def display_trends(days:int|None=None,start_date:str|None=None,end_date:str|None=None,lot_ids:list[str]|None=None,product_ids:list[str]|None=None,layer_ids:list[str]|None=None,exposure_equipment_ids:list[str]|None=None,s=Depends(dep)):return s.trends(TrendQueryRequest(days=days,start_date=start_date,end_date=end_date,lot_ids=lot_ids or [],product_ids=product_ids or [],layer_ids=layer_ids or [],exposure_equipment_ids=exposure_equipment_ids or []))
@app.post("/trends/query",response_model=TrendResponse)
def query_trends(q:TrendQueryRequest,s=Depends(dep)):return s.trends(q)
@app.post("/trends/distribution",response_model=DistributionStats)
def distribution(q:TrendQueryRequest,s=Depends(dep)):return s.distribution(q)
@app.post("/workspaces",response_model=WorkspaceResponse,status_code=201)
def create_workspace(s=Depends(dep)):return s.create_workspace()
@app.post("/workspaces/{workspace_id}/filters",response_model=WorkspaceFiltersResponse)
def filters(workspace_id:str,r:WorkspaceFiltersRequest,s=Depends(dep)):
 try:return s.add_filters(workspace_id,r.filters)
 except WorkspaceNotFoundError as exc:raise HTTPException(404,str(exc)) from exc
@app.get("/workspaces/{workspace_id}/connection-info",response_model=WorkspaceConnectionInfo)
def connection(workspace_id:str,s=Depends(dep)):
 try:return s.connection_info(workspace_id)
 except WorkspaceNotFoundError as exc:raise HTTPException(404,str(exc)) from exc
@app.post("/workspaces/{workspace_id}/registrations",response_model=RegistrationStatus,status_code=202)
def register(workspace_id:str,r:RegistrationRequest,s=Depends(dep)):
 try:return s.register(workspace_id,r)
 except WorkspaceNotFoundError as exc:raise HTTPException(404,str(exc)) from exc
@app.get("/workspaces/{workspace_id}/registrations/{registration_id}",response_model=RegistrationStatus)
def registration(workspace_id:str,registration_id:str,s=Depends(dep)):
 try:return s.registration(workspace_id,registration_id)
 except RegistrationNotFoundError as exc:raise HTTPException(404,str(exc)) from exc
@app.post("/wafers/query",response_model=WaferQueryResponse)
def wafers(r:WaferQueryRequest,s=Depends(dep)):
 try:return s.wafers(r)
 except WorkspaceNotFoundError as exc:raise HTTPException(404,str(exc)) from exc
