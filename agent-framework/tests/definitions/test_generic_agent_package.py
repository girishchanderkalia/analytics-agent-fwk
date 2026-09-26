from pathlib import Path
import sys, pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'agent-runtime'))
from definitions import AgentPackageError, AgentPackageManifestError, load_agent_package
def package(tmp_path,manifest=None):
 r=tmp_path/'pkg';r.mkdir();(r/'graph.yaml').write_text('entry: start\n');(r/'state.yaml').write_text('type: object\n');(r/'notes.md').write_text('docs\n')
 (r/'agent-package.yaml').write_text(manifest or 'kind: agent-package\nid: example-agent\nversion: "1.0"\nsources:\n  graph: graph.yaml\n  state: state.yaml\n  documentation:\n    - notes.md\n')
 return r
def test_loads_generic_sources(tmp_path):
 p=load_agent_package(package(tmp_path));assert p.source('graph').name=='graph.yaml';assert p.manifest.agent_id=='example-agent'
def test_docs_not_runtime_source(tmp_path):
 p=load_agent_package(package(tmp_path));assert {r for r,_ in p.manifest.sources.runtime_sources()}=={'graph','state'}
def test_missing_state_role(tmp_path):
 with pytest.raises(AgentPackageManifestError,match='state'):load_agent_package(package(tmp_path,'id: a\nversion: "1"\nsources:\n  graph: graph.yaml\n'))
def test_escape_rejected(tmp_path):
 (tmp_path/'outside.yaml').write_text('x')
 with pytest.raises(AgentPackageManifestError,match='escapes'):load_agent_package(package(tmp_path,'id: a\nversion: "1"\nsources:\n  graph: ../outside.yaml\n  state: state.yaml\n'))
def test_missing_source_rejected(tmp_path):
 r=package(tmp_path);(r/'graph.yaml').unlink()
 with pytest.raises(AgentPackageError,match='graph'):load_agent_package(r)
