import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'agent-runtime'))
from mcp_tools import *
def tool(name='read_data',version='1',server='data'):return McpToolDescriptor(McpToolKey(name,version,server),'Read data',{'type':'object'},{'type':'object'})
def test_register_and_require():
 r=McpToolRegistry();d=tool();r.register_many([d]);assert r.require(d.key) is d
def test_duplicate_registration_is_atomic():
 r=McpToolRegistry();r.register_many([tool('first')])
 with pytest.raises(DuplicateMcpToolError):r.register_many([tool('second'),tool('first')])
 assert [x.key.name for x in r.snapshot()]==['first']
def test_missing_tool():
 with pytest.raises(McpToolNotFoundError):McpToolRegistry().resolve(AgentToolReference('missing','1'))
def test_server_disambiguation():
 r=McpToolRegistry();r.register_many([tool(server='one'),tool(server='two')])
 with pytest.raises(McpToolAllowlistError):r.resolve(AgentToolReference('read_data','1'))
 assert r.resolve(AgentToolReference('read_data','1','two')).key.server=='two'
def test_allowlist_order():
 r=McpToolRegistry();r.register_many([tool('first'),tool('second')]);assert [x.key.name for x in r.select([AgentToolReference('second','1'),AgentToolReference('first','1')])]==['second','first']
def test_duplicate_allowlist():
 r=McpToolRegistry();r.register_many([tool()]);ref=AgentToolReference('read_data','1')
 with pytest.raises(McpToolAllowlistError):r.select([ref,ref])
