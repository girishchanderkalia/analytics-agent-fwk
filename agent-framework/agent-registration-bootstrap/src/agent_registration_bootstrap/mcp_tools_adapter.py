from __future__ import annotations


class McpToolRegistryAvailability:
    """Adapter for the existing Slice 13D McpToolRegistry."""

    def __init__(self, registry) -> None:
        self._registry = registry

    def contains(self, *, name: str, version: str, server: str) -> bool:
        return any(
            descriptor.key.name == name
            and descriptor.key.version == version
            and descriptor.key.server == server
            for descriptor in self._registry.snapshot()
        )
