"""Tests for final fixed per-agent runtime composition."""
from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace
V3_ROOT=Path(__file__).resolve().parents[1]
AR=V3_ROOT/"agent-runtime"
if str(AR) not in sys.path: sys.path.insert(0,str(AR))
from host.runtime_context_factory import ExecutionSecurityContext, RuntimeContextFactory

class FakeContextFactory:
    def __init__(self): self.bundles=[]
    def create(self,bundle): self.bundles.append(bundle); return object()

def test_security_context_normalizes_sets():
    value=ExecutionSecurityContext(permissions={"read"},approved_capabilities={"write"})
    assert value.permissions==frozenset({"read"})
    assert value.approved_capabilities==frozenset({"write"})

def test_security_context_defaults_are_empty():
    value=ExecutionSecurityContext()
    assert value.permissions==frozenset()
    assert value.approved_capabilities==frozenset()

def test_factory_uses_security_context(monkeypatch):
    import host.runtime_context_factory as module
    monkeypatch.setattr(module,"create_capability_dispatcher",lambda value:value)
    monkeypatch.setattr(module,"create_operation_registry",lambda value:value)
    monkeypatch.setattr(module,"validate_workflow_operations",lambda bundle,operations:None)
    class Cache:
        def get_or_create(self,bundle): return "contracts"
    security=ExecutionSecurityContext({"read"},{"write"})
    factory=RuntimeContextFactory(object(),{},security_context=security,model_gateway=object(),contract_provider_cache=Cache())
    bundle=SimpleNamespace()
    context=factory.create(bundle)
    assert context.permissions==frozenset({"read"})
    assert context.approved_capabilities==frozenset({"write"})
    assert context.contract_provider=="contracts"
