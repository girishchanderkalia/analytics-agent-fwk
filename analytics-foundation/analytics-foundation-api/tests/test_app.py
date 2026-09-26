from fastapi.testclient import TestClient
from foundation_api.app import app,dep
from foundation_api.repositories.json_repository import JsonFoundationRepository
from foundation_api.service import FoundationService
def test_routes(data_dir):
 s=FoundationService(JsonFoundationRepository(data_dir),"trend","wafer");app.dependency_overrides[dep]=lambda:s
 try:
  client=TestClient(app);assert client.get("/health").status_code==200;assert client.get("/ready").status_code==200;assert client.post("/trends/query",json={}).json()["series"];wid=client.post("/workspaces").json()["workspace_id"];assert client.post(f"/workspaces/{wid}/filters",json={"filters":{"machine":"M1"}}).status_code==200;assert client.post("/wafers/query",json={"workspace_id":wid,"table":"wafer","filters":{"machine":"M1"}}).json()["anomalous_wafers"]==["W1"]
 finally:app.dependency_overrides.clear()
