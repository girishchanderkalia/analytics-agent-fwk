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


def test_wafer_preview_matches_all_highlighted_scopes_without_duplicates():
 class Repository:
  def wafer_rows(self):
   return [
    {"lot_id":"lot1","layer_id":"layer1","exposure_equipment_id":"M1","wafer_id":"W1","overlay_x":1,"overlay_y":0},
    {"lot_id":"lot2","layer_id":"layer2","exposure_equipment_id":"M2","wafer_id":"W2","overlay_x":1,"overlay_y":0},
    {"lot_id":"other","layer_id":"layer1","exposure_equipment_id":"M1","wafer_id":"W3","overlay_x":1,"overlay_y":0},
   ]
 service=FoundationService(Repository(),"trend","wafer")
 scopes=[{"lot_id":"lot1","layer_id":"layer1","machine":"M1"},{"lot_id":"lot2","layer_id":"layer2","machine":"M2"},{"lot_id":"lot1","layer_id":"layer1","machine":"M1"}]
 result=service.wafers(WaferQueryRequest(workspace_id="TREND_PREVIEW",table="wafer",filters={"outlier_scopes":scopes}))
 assert {row["lot_id"] for row in result.rows}=={"lot1","lot2"}
 assert len(result.rows)==2
 assert set(result.anomalous_wafers)=={"W1","W2"}
 assert service.wafers(WaferQueryRequest(workspace_id="TREND_PREVIEW",table="wafer",filters={"outlier_scopes":[]})).rows==[]


def test_wafer_preview_rejects_unscoped_candidates(data_dir):
 import pytest
 service=svc(data_dir)
 with pytest.raises(ValueError,match="must identify a lot"):
  service.wafers(WaferQueryRequest(workspace_id="TREND_PREVIEW",table="wafer",filters={"outlier_scopes":[{"machine":"M1"}]}))
