from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/"agent-runtime"))
from host.langgraph_service import CompiledAgentCache, CompiledAgentCacheKey

def test_cache_and_invalidate():
    cache=CompiledAgentCache(); key=CompiledAgentCacheKey("a","1","x"); calls=[]
    first=cache.get_or_create(key,lambda:(calls.append(1) or object())); second=cache.get_or_create(key,lambda:object())
    assert first is second; assert len(calls)==1; assert cache.invalidate(agent_id="a")==1
