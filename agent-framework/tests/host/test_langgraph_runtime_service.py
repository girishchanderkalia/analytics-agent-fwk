from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/"agent-runtime"))
from host.langgraph_service import AgentVersionReference, AgentVersionResolver, LangGraphChatCommand, LangGraphResumeCommand, LangGraphRuntimeService
from host.langgraph_service.sqlite_metadata_store import SQLiteConversationMetadataStore

class Repository:
    ref=AgentVersionReference("agent","1.0","sha256:x",{"id":"agent"})
    def get_active(self,agent_id): return self.ref
    def get_version(self,agent_id,version): return self.ref
class Compiled:
    def invoke(self,**kwargs): return {"status":"waiting_for_approval","finding":"candidate","__interrupt__":[{"approvalId":"approve"}]}
    def resume(self,**kwargs): return {"status":"completed","finding":"done"}
class Compiler:
    calls=0
    def compile(self,**kwargs): self.calls+=1; return Compiled()
class Deps:
    def create(self,definition): return object()

def test_start_and_resume(tmp_path):
    compiler=Compiler(); store=SQLiteConversationMetadataStore(tmp_path/"meta.sqlite")
    service=LangGraphRuntimeService(resolver=AgentVersionResolver(Repository()),compiler=compiler,dependency_factory=Deps(),checkpointer=object(),metadata_store=store)
    started=service.start_chat(LangGraphChatCommand("agent","question"))
    assert started.status=="waiting_for_approval"; assert started.agent_version=="1.0"
    resumed=service.resume(LangGraphResumeCommand(started.conversation_id,True,expected_version=1))
    assert resumed.status=="completed"; assert resumed.version==2; assert compiler.calls==1
