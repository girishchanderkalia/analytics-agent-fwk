from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/"agent-runtime"))
from host.langgraph_service import LangGraphResultMapper

def test_mapper_hides_internal_fields():
    status,result,approval=LangGraphResultMapper().map({"status":"completed","finding":"x","thread_id":"secret","checkpoint_id":"secret"})
    assert status=="completed"; assert result=={"status":"completed","finding":"x"}; assert approval is None
