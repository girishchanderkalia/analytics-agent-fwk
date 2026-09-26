from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping
from .errors import InvalidMcpToolError
def _t(v,n):
 if not isinstance(v,str) or not v.strip(): raise InvalidMcpToolError(f"{n} must be non-empty")
 return v.strip()
@dataclass(frozen=True,order=True)
class McpToolKey:
 name:str;version:str;server:str
 def __post_init__(self):
  object.__setattr__(self,'name',_t(self.name,'name'));object.__setattr__(self,'version',_t(self.version,'version'));object.__setattr__(self,'server',_t(self.server,'server'))
@dataclass(frozen=True)
class McpToolDescriptor:
 key:McpToolKey;description:str;input_schema:Mapping[str,Any];output_schema:Mapping[str,Any]|None=None;annotations:Mapping[str,Any]=field(default_factory=dict)
 def __post_init__(self):
  if not isinstance(self.input_schema,Mapping): raise InvalidMcpToolError('input_schema must be a mapping')
  object.__setattr__(self,'input_schema',dict(self.input_schema));object.__setattr__(self,'output_schema',None if self.output_schema is None else dict(self.output_schema));object.__setattr__(self,'annotations',dict(self.annotations))
@dataclass(frozen=True)
class AgentToolReference:
 name:str;version:str;server:str|None=None
class MCPApprovalMode(StrEnum): NEVER='never';ALWAYS='always';WRITE='write'
@dataclass(frozen=True)
class MCPServerRegistration:
 server_id:str;display_name:str;transport:str;endpoint:str;enabled:bool=True;authentication_profile:str|None=None;timeout_seconds:float=30.0;metadata:Mapping[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class MCPToolRegistration:
 tool_id:str;server_id:str;remote_name:str;title:str;description:str;input_schema:Mapping[str,Any];output_schema:Mapping[str,Any]|None=None;required_permissions:frozenset[str]=frozenset();approval_mode:MCPApprovalMode=MCPApprovalMode.NEVER;enabled:bool=True;mutating:bool=False;timeout_seconds:float|None=None;tags:frozenset[str]=frozenset()
@dataclass(frozen=True)
class MCPToolSecurityContext:
 agent_id:str;conversation_id:str;permissions:frozenset[str]=frozenset();approved_tools:frozenset[str]=frozenset();allowed_tools:frozenset[str]=frozenset();user_id:str|None=None
