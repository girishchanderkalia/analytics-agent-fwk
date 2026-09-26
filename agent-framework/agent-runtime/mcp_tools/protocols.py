from collections.abc import Iterable
from typing import Protocol
from .models import McpToolDescriptor
class McpToolDiscoveryClient(Protocol):
 async def discover_tools(self)->Iterable[McpToolDescriptor]:...
