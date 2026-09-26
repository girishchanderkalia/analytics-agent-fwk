class McpToolDiscoveryService:
 def __init__(self,client,registry):self.client=client;self.registry=registry
 async def refresh(self):
  items=tuple(await self.client.discover_tools());self.registry.replace_all(items);return len(items)
