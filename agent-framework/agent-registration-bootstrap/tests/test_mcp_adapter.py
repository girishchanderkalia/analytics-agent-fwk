from dataclasses import dataclass

from agent_registration_bootstrap.mcp_tools_adapter import McpToolRegistryAvailability


@dataclass(frozen=True)
class Key:
    name: str
    version: str
    server: str


@dataclass(frozen=True)
class Descriptor:
    key: Key


class Registry:
    def snapshot(self):
        return (Descriptor(Key("query_trends", "1", "analytics-foundation")),)


def test_mcp_registry_adapter_matches_full_identity() -> None:
    availability = McpToolRegistryAvailability(Registry())
    assert availability.contains(name="query_trends", version="1", server="analytics-foundation")
    assert not availability.contains(name="query_trends", version="2", server="analytics-foundation")
