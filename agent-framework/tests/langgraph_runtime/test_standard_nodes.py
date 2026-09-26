from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace
from pydantic import BaseModel
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/"agent-runtime"))
from langgraph_runtime.nodes import create_approval_node, create_condition_router, create_contract_validation_node, create_copy_node, create_structured_model_node, create_tool_node
from langgraph_runtime.nodes.library import StandardNodeLibrary

class Result(BaseModel): value: int
class PromptProvider:
    def get_prompt(self, name): return "system"
class ContractProvider:
    def get_contract(self, name): return Result
class ModelProvider:
    def invoke_structured(self, **kwargs): return {"value": 3}
class ToolRegistry:
    def invoke(self, **kwargs): return {"rows": [kwargs["arguments"]]}
class Expressions:
    def evaluate(self, condition, state): return state[condition]

def deps(): return SimpleNamespace(prompt_provider=PromptProvider(),contract_provider=ContractProvider(),model_provider=ModelProvider(),tool_registry=ToolRegistry(),expression_engine=Expressions(),security_context={})
def test_model_node(): assert create_structured_model_node(dependencies=deps(),prompt_id="p",contract_id="c",output_field="answer")({"question":"q"}) == {"answer":{"value":3}}
def test_tool_node(): assert create_tool_node(dependencies=deps(),tool_id="query.read",input_mapping={"filters":"filters"},output_field="data")({"filters":{"days":7}})["data"]["rows"][0]=={"filters":{"days":7}}
def test_validation_node(): assert create_contract_validation_node(dependencies=deps(),source_path="candidate",contract_id="c")({"candidate":{"value":4}})=={"candidate":{"value":4}}
def test_approval_node():
    calls=[]
    node=create_approval_node(approval_id="approve",payload_mapping={"candidate":"candidate"},interrupt_function=lambda request:(calls.append(request) or {"approved":True,"comment":"ok"}))
    assert node({"candidate":{"id":"x"}})["approved"] is True; assert calls[0]["payload"]["candidate"]=={"id":"x"}
def test_router_and_copy():
    copied=create_copy_node({"selected":"nested.value"})({"nested":{"value":5}}); assert copied=={"selected":5}
    router=create_condition_router(dependencies=deps(),routes=(("go","next"),),default_destination="end"); assert router({"go":True})=="next"
def test_library_types(): assert StandardNodeLibrary().list_types()==("approval","assign","copy","model","status","tool","validate")
