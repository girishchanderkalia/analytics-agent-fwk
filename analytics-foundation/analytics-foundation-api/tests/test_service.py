from foundation_api.models import *
from foundation_api.repositories.json_repository import JsonFoundationRepository
from foundation_api.service import FoundationService
def svc(data_dir):return FoundationService(JsonFoundationRepository(data_dir),"trend","wafer")
def test_health_data_and_distribution(data_dir):
 s=svc(data_dir);s.ready();result=s.trends(TrendQueryRequest(exposure_equipment_ids=["M1"]));assert len(result.series)==1;stats=s.distribution(TrendQueryRequest());assert stats.sample_count==2 and stats.p95==3.4
def test_workspace_registration_and_connection(data_dir):
 s=svc(data_dir);wid=s.create_workspace().workspace_id;assert s.add_filters(wid,{"machine":"M1"}).filters=={"machine":"M1"};assert s.connection_info(wid).workspace_id==wid;reg=s.register(wid,RegistrationRequest(dataset="overlay",table="wafer"));assert reg.status=="READY" and s.registration(wid,reg.registration_id)==reg
def test_wafer_query_and_anomaly(data_dir):
 s=svc(data_dir);wid=s.create_workspace().workspace_id;result=s.wafers(WaferQueryRequest(workspace_id=wid,table="wafer",filters={"machine":"M1"}));assert result.anomalous_wafers==["W1"] and len(result.rows)==1
