from fastapi.testclient import TestClient
from opo_capability_service.app import create_app

def test_tool_catalog_matches_slice_13g():
    client=TestClient(create_app())
    body=client.post("/mcp",json={"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}).json()
    assert {tool["name"] for tool in body["result"]["tools"]}=={"analyze_trends","normalize_wafer_evidence","classify_spatial_pattern"}

def test_tools_call_returns_structured_content():
    client=TestClient(create_app())
    body=client.post("/mcp",json={"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"classify_spatial_pattern","arguments":{"rows":[],"anomalous_wafer_ids":[]}}}).json()
    assert body["result"]["structuredContent"]["pattern"]=="no_data"
    assert body["result"]["isError"] is False

def test_unknown_tool_is_protocol_error():
    client=TestClient(create_app())
    body=client.post("/mcp",json={"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"missing","arguments":{}}}).json()
    assert body["error"]["code"]==-32602

def test_health_and_ready():
    client=TestClient(create_app())
    assert client.get("/health").status_code==200
    assert client.get("/ready").json()=={"status":"ready","tools":3}
