from pathlib import Path
import sys
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'agent-runtime'))
from agent_registration import AgentRegistrationService, GenericAgentPackageRegistrationValidator, InMemoryAgentRegistrationCatalog
from api.app import create_app

def package(tmp_path):
    root=tmp_path/'pkg';root.mkdir();(root/'graph.yaml').write_text('entry: start\n');(root/'state.yaml').write_text('type: object\n');(root/'agent-package.yaml').write_text('id: example-agent\nversion: "1.0"\nsources:\n  graph: graph.yaml\n  state: state.yaml\n');return root

def api():
    return TestClient(create_app(AgentRegistrationService(InMemoryAgentRegistrationCatalog(),GenericAgentPackageRegistrationValidator())))

def test_bulk_registration_and_listing(tmp_path):
    response=api().post('/v1/applications/example-app/agents:bulk-register',json={'agents':[{'agentId':'example-agent','version':'1.0','packageRoot':str(package(tmp_path))}]})
    assert response.status_code==201
    assert response.json()['agents'][0]['agentId']=='example-agent'

def test_unconfigured_service_is_503():
    assert TestClient(create_app()).get('/v1/applications/app/agents').status_code==503

def test_invalid_package_is_422(tmp_path):
    response=api().post('/v1/applications/app/agents:bulk-register',json={'agents':[{'agentId':'x','version':'1','packageRoot':str(tmp_path/'missing')}]})
    assert response.status_code==422
