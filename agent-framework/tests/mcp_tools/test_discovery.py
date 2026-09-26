import asyncio,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'agent-runtime'))
from mcp_tools import *
class Client:
 async def discover_tools(self):return [McpToolDescriptor(McpToolKey('read','1','server'),'Read',{'type':'object'})]
def test_refresh():
 r=McpToolRegistry();assert asyncio.run(McpToolDiscoveryService(Client(),r).refresh())==1;assert r.snapshot()[0].key.name=='read'
