from foundation_api.models import *
from foundation_api.repositories.json_repository import JsonFoundationRepository
from foundation_api.service import FoundationService
from foundation_api.overlay import METRIC_COLUMNS,OverlayQueryRequest
import json
import pytest
import sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
def svc(data_dir):return FoundationService(JsonFoundationRepository(data_dir),"trend","wafer")
def test_health_data_and_distribution(data_dir):
 s=svc(data_dir);s.ready();result=s.trends(TrendQueryRequest(exposure_equipment_ids=["M1"]));assert len(result.series)==1;stats=s.distribution(TrendQueryRequest());assert stats.sample_count==2 and stats.p95==3.4
def test_workspace_registration_and_connection(data_dir):
 s=svc(data_dir);wid=s.create_workspace().workspace_id;assert s.add_filters(wid,{"machine":"M1"}).filters=={"machine":"M1"};assert s.connection_info(wid).workspace_id==wid;reg=s.register(wid,RegistrationRequest(dataset="overlay",table="wafer"));assert reg.status=="READY" and s.registration(wid,reg.registration_id)==reg
def test_wafer_query_and_anomaly(data_dir):
 s=svc(data_dir);wid=s.create_workspace().workspace_id;result=s.wafers(WaferQueryRequest(workspace_id=wid,table="wafer",filters={"machine":"M1"}));assert result.anomalous_wafers==["W1"] and len(result.rows)==1

@pytest.fixture
def overlay_data(data_dir):
 tables={
  "lot_step":[{"id":2},{"id":1},{"id":3}],
  "lot_exposure_step":[{"id":10,"lot_step_id":1,"product_id":"P1","key_lot_id":"L1","key_layer_id":"Y1","machine_id":"M1","lot_start":"2026-01-29 14:02:30+00"}],
  "lot_metrology_step":[{"id":20,"lot_step_id":1,"machine_id":"MET1"},{"id":21,"lot_step_id":2}],
  "lot_kpi_mapping":[{"id":30,"lot_metrology_step_id":20,"aggregation_level":"LOT"},{"id":31,"lot_metrology_step_id":20,"aggregation_level":"WAFER"},{"id":32,"lot_metrology_step_id":21,"aggregation_level":"LOT"},{"id":33,"lot_metrology_step_id":20,"aggregation_level":"LOT"},{"id":34,"lot_metrology_step_id":None,"aggregation_level":"LOT"}],
  "lot_metrology_overlay_kpis":[{"id":identity,**{prefix+"_"+axis:float(index) if axis=="x" else -float(index) for index,prefix in enumerate(METRIC_COLUMNS.values(),1) for axis in ("x","y")}} for identity in (30,31,32,34)],
  "exposure_machine":[{"id":"M1","customername":"Scanner 1"}],
 }
 tables["lot_exposure_step"].append(dict(tables["lot_exposure_step"][0]))
 for name,rows in tables.items():(data_dir/(name+".json")).write_text(json.dumps(rows))
 return data_dir

@pytest.mark.parametrize("metric,index",list(zip(METRIC_COLUMNS,range(1,6))))
def test_overlay_metrics_and_joins(overlay_data,metric,index):
 result=svc(overlay_data).overlay_trends(OverlayQueryRequest(metric=metric))
 assert [point.lot_step_id for point in result.points]==[1,2]
 point=result.points[0]
 assert (point.kpi_x,point.kpi_y)==(index,-index)
 assert point.exposure_equipment_id=="Scanner 1" and point.metrology_equipment_id=="MET1"
 assert not point.needs_ingestion
 assert result.points[1].lot_id is None

def test_overlay_filters(overlay_data):
 service=svc(overlay_data)
 assert len(service.overlay_trends(OverlayQueryRequest(start_date="2026-01-29",end_date="2026-01-29",lot_ids=["L1"],product_ids=["P1"],layer_ids=["Y1"],exposure_equipment_ids=["Scanner 1"])).points)==1
 for filters in ({"excluded_product_ids":["P1"],"lot_ids":["L1"]},{"start_date":"2026-01-30"},{"end_date":"2026-01-28"},{"lot_ids":["missing"]}):
  assert not service.overlay_trends(OverlayQueryRequest(**filters)).points
 with pytest.raises(ValueError):OverlayQueryRequest(metric="UNKNOWN")
 with pytest.raises(ValueError):OverlayQueryRequest(start_date="2026-02-01",end_date="2026-01-01")

@pytest.mark.parametrize("metric,prefix",list(METRIC_COLUMNS.items()))
def test_imported_overlay_matches_sql(metric,prefix):
 repository=JsonFoundationRepository(Path(__file__).resolve().parents[1]/"data")
 with sqlite3.connect(":memory:") as database:
    for table in ("lot_step","lot_exposure_step","lot_metrology_step","lot_kpi_mapping","lot_metrology_overlay_kpis","exposure_machine"):
     rows=repository.table_rows(table)
     columns=list(rows[0])
     database.execute(f'CREATE TABLE "{table}" ({", ".join(columns)})')
     database.executemany(f'INSERT INTO "{table}" VALUES ({", ".join("?" for column in columns)})',[[row.get(column) for column in columns] for row in rows])
    expected=database.execute(f'''
     SELECT DISTINCT lot.id, metrology.id, exposure.product_id, exposure.key_lot_id,
        exposure.key_layer_id, exposure.machine_id, COALESCE(NULLIF(machine.customername, ''), exposure.machine_id),
        metrology.machine_id, kpis.{prefix}_x, kpis.{prefix}_y
     FROM lot_step lot
     LEFT JOIN lot_exposure_step exposure ON lot.id = exposure.lot_step_id
     LEFT JOIN lot_metrology_step metrology ON lot.id = metrology.lot_step_id
     INNER JOIN lot_kpi_mapping mapping ON metrology.id = mapping.lot_metrology_step_id AND mapping.aggregation_level = 'LOT'
     INNER JOIN lot_metrology_overlay_kpis kpis ON mapping.id = kpis.id
     LEFT JOIN exposure_machine machine ON machine.id = exposure.machine_id
     ORDER BY lot.id
    ''').fetchall()
 result=FoundationService(repository,"trend","wafer").overlay_trends(OverlayQueryRequest(metric=metric))
 actual=[(point.lot_step_id,point.lot_metrology_step_id,point.product_id,point.lot_id,point.layer_id,point.exposure_machine_id,point.exposure_equipment_id,point.metrology_equipment_id,point.kpi_x,point.kpi_y) for point in result.points]
 assert expected and actual==expected

def test_overlay_http_contract(overlay_data):
 from foundation_api.app import app,dep
 app.dependency_overrides[dep]=lambda:svc(overlay_data)
 try:
    with TestClient(app) as client:
     response=client.post("/overlay/trends/query",json={"metric":"MAX_997"})
     assert response.status_code==200
     assert response.json()["points"][0]["kpi_x"]==5
     assert response.json()["points"][0]["lot_start"]=="2026-01-29T14:02:30Z"
     assert client.post("/overlay/trends/query",json={"metric":"UNKNOWN"}).status_code==422
     assert client.post("/overlay/trends/query",json={"start_date":"invalid"}).status_code==422
     (overlay_data/"lot_kpi_mapping.json").unlink()
     assert client.post("/overlay/trends/query",json={}).status_code==503
 finally:app.dependency_overrides.pop(dep,None)
