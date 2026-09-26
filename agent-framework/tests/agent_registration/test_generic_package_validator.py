from pathlib import Path
import sys, pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'agent-runtime'))
from agent_registration import AgentRegistrationRequest, AgentRegistrationValidationError, GenericAgentPackageRegistrationValidator
def package(tmp_path):
 r=tmp_path/'pkg';r.mkdir();(r/'graph.yaml').write_text('entry: start\n');(r/'state.yaml').write_text('type: object\n');(r/'agent-package.yaml').write_text('id: example-agent\nversion: "1.0"\nsources:\n  graph: graph.yaml\n  state: state.yaml\n');return r
def request(root,agent='example-agent',version='1.0'):return AgentRegistrationRequest(agent,version,root)
def test_stable_fingerprint(tmp_path):
 r=package(tmp_path);v=GenericAgentPackageRegistrationValidator();assert v.validate(application_id='app',request=request(r))==v.validate(application_id='app',request=request(r))
def test_source_change_changes_fingerprint(tmp_path):
 r=package(tmp_path);v=GenericAgentPackageRegistrationValidator();a=v.validate(application_id='app',request=request(r));(r/'graph.yaml').write_text('changed\n');assert a!=v.validate(application_id='app',request=request(r))
def test_identity_mismatch(tmp_path):
 with pytest.raises(AgentRegistrationValidationError,match='agent ID'):GenericAgentPackageRegistrationValidator().validate(application_id='app',request=request(package(tmp_path),'other'))
def test_version_mismatch(tmp_path):
 with pytest.raises(AgentRegistrationValidationError,match='version'):GenericAgentPackageRegistrationValidator().validate(application_id='app',request=request(package(tmp_path),version='2'))
