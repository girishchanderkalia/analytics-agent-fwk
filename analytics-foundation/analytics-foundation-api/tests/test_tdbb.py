import json
from fastapi.testclient import TestClient
from foundation_api.app import app,dep
from foundation_api.models import TdbbRunRequest,TrendQueryRequest
from foundation_api.repositories.json_repository import JsonFoundationRepository
from foundation_api.service import FoundationService

SCOPE={"product_id":"AAA2","layer_id":"OV_NO_ID2","exposure_equipment_id":"GW021"}
LOTS=(("LotOV1001","2026-08-20"),("LotOV1002","2026-08-25"),("LotOV1003","2026-09-03"),("LotOV1004","2026-09-10"))

def _run(lot,day):
 return {**SCOPE,"run_id":f"run-{lot}","status":"COMPLETED","model_step":"10par","context_levels":["AVG","W2W"],"lot_id":lot,"lot_start":f"{day}T06:00:00+00:00","wafers":[{"wafer_id":f"Carrier {lot[-3:]}.{i}","chuck_id":f"Waferstage chuck ID {i}"} for i in (1,2)]}

def _service(tmp_path):
 trends=[{"productId":run["product_id"],"layerId":run["layer_id"],"exposureEquipmentId":run["exposure_equipment_id"],"lotId":run["lot_id"],"waferId":w["wafer_id"],"chuckId":w["chuck_id"],"lotStart":run["lot_start"],"kpiValue1":2.5,"kpiValue2":2.6} for run in (_run(*lot) for lot in LOTS) for w in run["wafers"]]
 (tmp_path/"trend_rows.json").write_text(json.dumps(trends))
 (tmp_path/"tdbb_runs_v3.json").write_text(json.dumps([_run(*lot) for lot in LOTS]))
 return FoundationService(JsonFoundationRepository(tmp_path),"trend","wafer")

def test_trend_points_carry_x_y_and_filter_by_chuck(tmp_path):
 series=_service(tmp_path).trends(TrendQueryRequest(chuck_ids=["Waferstage chuck ID 2"])).series
 points=[p for s in series for p in s.points]
 assert len(points)==4 and {p.chuck_id for p in points}=={"Waferstage chuck ID 2"} and points[0].kpi_value_y==2.6

def test_run_request_resolves_existing_runs_before_and_after_change_date(tmp_path):
 result=_service(tmp_path).run_tdbb(TdbbRunRequest(start_date="2026-08-17",end_date="2026-09-16",change_date="2026-09-01",product_ids=["AAA2"]))
 before,after=result.periods
 assert (before.end_date,before.run_ids,before.wafer_count)==("2026-08-31",["run-LotOV1001","run-LotOV1002"],4)
 assert (after.start_date,after.run_ids)==("2026-09-01",["run-LotOV1003","run-LotOV1004"])
 assert [b.budget for b in after.budgets][:5]==["nce_wafer.average","nce_field.average","ce_wafer.average","ce_field.average","ce_translation.average"]
 assert {b.context for b in after.budgets}=={"average","chuck_to_chuck","lot_to_lot","wafer_to_wafer"} and len(after.budgets)==20
 nce=lambda period:next(b for b in period.budgets if b.budget=="nce_wafer.average")
 assert nce(after).x_m3s>nce(before).x_m3s
 assert {(m.budget,m.period,m.level) for m in result.maps}>={("nce_wafer.average","before","wafer"),("nce_field.average","after","field")}
 assert not any(m.budget.startswith("ce_translation") for m in result.maps)

def test_chuck_filter_limits_wafers_in_resolved_runs(tmp_path):
 result=_service(tmp_path).run_tdbb(TdbbRunRequest(start_date="2026-08-17",end_date="2026-09-16",change_date="2026-09-01",chuck_ids=["Waferstage chuck ID 1"]))
 assert [p.wafer_count for p in result.periods]==[2,2]

def test_run_data_follows_real_tdbb_schema(tmp_path):
 data=_service(tmp_path).tdbb_data("run-LotOV1001")
 assert set(data.tables)=={"ce_wafer","ce_field","nce_wafer","nce_field"}
 nce=data.tables["nce_wafer"]
 assert {r["context_level"] for r in nce}=={"AVG","W2W"} and {r["virtual_dataset_id"] for r in nce}=={"1","2","3"}
 assert {"nce_wafer_x","nce_wafer_y","field_center_x","intrafield_position_x","wafer_diameter","lot_id","wafer_id","chuck_id"}<=set(nce[0])
 assert data.tables["ce_wafer"][0]["model_step"]=="10par" and data.tables["nce_field"][0]["model_step"] is None
 w2w=[r["nce_wafer_x"] for r in nce if r["context_level"]=="W2W" and r["field_center_x"]==nce[0]["field_center_x"] and r["field_center_y"]==nce[0]["field_center_y"] and r["intrafield_position_x"]==nce[0]["intrafield_position_x"] and r["intrafield_position_y"]==nce[0]["intrafield_position_y"]]
 assert abs(sum(w2w))<1e-5

def test_tdbb_routes(tmp_path):
 s=_service(tmp_path);app.dependency_overrides[dep]=lambda:s
 try:
  client=TestClient(app)
  assert client.post("/tdbb/runs",json={"start_date":"2026-08-17","end_date":"2026-09-16","change_date":"2026-09-20"}).status_code==422
  created=client.post("/tdbb/runs",json={"start_date":"2026-08-17","end_date":"2026-09-16","change_date":"2026-09-01"})
  run_id=created.json()["periods"][0]["run_ids"][0]
  assert created.status_code==201 and client.get(f"/tdbb/runs/{run_id}").json()["lot_id"]=="LotOV1001"
  data=client.get(f"/tdbb/runs/{run_id}/data",params={"tables":["nce_wafer"]}).json()
  assert list(data["tables"])==["nce_wafer"]
  assert client.get(f"/tdbb/runs/{run_id}/data",params={"tables":["bogus"]}).status_code==422
  assert client.get("/tdbb/runs/missing/data").status_code==404
 finally:app.dependency_overrides.clear()
