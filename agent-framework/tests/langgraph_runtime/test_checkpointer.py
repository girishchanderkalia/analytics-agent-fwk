from __future__ import annotations
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"agent-runtime"))
from langgraph_runtime.checkpointing import (
    CheckpointerBackend, CheckpointerFactory, CheckpointerSettings,
    CheckpointIdentity, CheckpointIdentityError,
)
from langgraph_runtime.checkpointing.runtime import CheckpointRuntime
from bootstrap.langgraph_checkpointer_bootstrap import create_langgraph_checkpointer

def test_identity_maps_conversation_to_internal_thread():
    config=CheckpointIdentity("conversation-1").configurable()
    assert config=={"configurable":{"thread_id":"conversation-1"}}

def test_identity_rejects_empty_conversation():
    with pytest.raises(CheckpointIdentityError): CheckpointIdentity(" ")

def test_memory_factory():
    handle=CheckpointerFactory().create(CheckpointerSettings())
    assert handle.checkpointer is not None
    handle.close()

def test_non_memory_requires_connection_string():
    with pytest.raises(ValueError,match="connection_string"):
        CheckpointerSettings(backend=CheckpointerBackend.POSTGRES).validate()

def test_environment_bootstrap_defaults_to_memory():
    handle=create_langgraph_checkpointer({})
    assert handle.checkpointer is not None

class Graph:
    def __init__(self): self.calls=[]
    def invoke(self,value,config): self.calls.append((value,config)); return {"ok":True}
    def get_state(self,config): self.calls.append(("get",config)); return {"state":True}

def test_runtime_hides_checkpoint_configuration():
    graph=Graph(); runtime=CheckpointRuntime(graph)
    assert runtime.start(conversation_id="public-id",state={"question":"q"})=={"ok":True}
    assert graph.calls[0][1]["configurable"]["thread_id"]=="public-id"
    assert runtime.get_state(conversation_id="public-id")=={"state":True}
