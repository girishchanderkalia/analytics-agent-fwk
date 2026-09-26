from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from .models import MCPServerRegistration
@dataclass(frozen=True)
class MCPDiscoveredTool:
 name:str;title:str|None;description:str|None;input_schema:Mapping[str,Any]
@dataclass(frozen=True)
class MCPToolResult:
 content:tuple[Mapping[str,Any],...]=();structured_content:Mapping[str,Any]|None=None;is_error:bool=False;metadata:Mapping[str,Any]=field(default_factory=dict)
class MCPClient(Protocol):
 def list_tools(self,*,server:MCPServerRegistration)->tuple[MCPDiscoveredTool,...]:...
 def call_tool(self,*,server:MCPServerRegistration,tool_name:str,arguments:Mapping[str,Any],timeout_seconds:float)->MCPToolResult:...
