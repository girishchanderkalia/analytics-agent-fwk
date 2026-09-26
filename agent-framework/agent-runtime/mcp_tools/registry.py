"""Thread-safe generic registry for discovered MCP tools."""

from __future__ import annotations

from collections.abc import Iterable
from threading import RLock

from .errors import (
    DuplicateMcpToolError,
    McpToolAllowlistError,
    McpToolNotFoundError,
)
from .models import AgentToolReference, McpToolDescriptor, McpToolKey


class McpToolRegistry:
    """Store and resolve domain-neutral MCP tool descriptors."""

    def __init__(self) -> None:
        self._tools: dict[McpToolKey, McpToolDescriptor] = {}
        self._lock = RLock()

    def replace_all(
        self,
        descriptors: Iterable[McpToolDescriptor],
    ) -> None:
        """Atomically replace all registered tools."""

        staged: dict[McpToolKey, McpToolDescriptor] = {}
        for descriptor in descriptors:
            if descriptor.key in staged:
                raise DuplicateMcpToolError(
                    f"Duplicate MCP tool: {_display(descriptor.key)}"
                )
            staged[descriptor.key] = descriptor

        with self._lock:
            self._tools = staged

    def register_many(
        self,
        descriptors: Iterable[McpToolDescriptor],
    ) -> None:
        """Atomically add tools without replacing existing keys."""

        with self._lock:
            staged = dict(self._tools)
            for descriptor in descriptors:
                if descriptor.key in staged:
                    raise DuplicateMcpToolError(
                        f"Duplicate MCP tool: {_display(descriptor.key)}"
                    )
                staged[descriptor.key] = descriptor
            self._tools = staged

    def require(self, key: McpToolKey) -> McpToolDescriptor:
        """Return one exactly identified tool."""

        with self._lock:
            try:
                return self._tools[key]
            except KeyError as exc:
                raise McpToolNotFoundError(
                    f"MCP tool is not registered: {_display(key)}"
                ) from exc

    def resolve(
        self,
        reference: AgentToolReference,
    ) -> McpToolDescriptor:
        """Resolve one allowlisted tool reference."""

        with self._lock:
            matches = [
                descriptor
                for key, descriptor in self._tools.items()
                if key.name == reference.name
                and key.version == reference.version
                and (
                    reference.server is None
                    or key.server == reference.server
                )
            ]

        if not matches:
            raise McpToolNotFoundError(
                f"MCP tool {reference.name!r} version "
                f"{reference.version!r} is not registered"
            )

        if len(matches) > 1:
            raise McpToolAllowlistError(
                f"MCP tool {reference.name!r} version "
                f"{reference.version!r} is ambiguous across servers"
            )

        return matches[0]

    def select(
        self,
        references: Iterable[AgentToolReference],
    ) -> tuple[McpToolDescriptor, ...]:
        """Resolve an allowlist while rejecting duplicate references."""

        requested = tuple(references)
        identities = [
            (
                reference.name,
                reference.version,
                reference.server,
            )
            for reference in requested
        ]

        if len(identities) != len(set(identities)):
            raise McpToolAllowlistError(
                "Agent tool allowlist contains duplicate references"
            )

        return tuple(
            self.resolve(reference)
            for reference in requested
        )

    def snapshot(self) -> tuple[McpToolDescriptor, ...]:
        """Return a stable snapshot ordered by tool key."""

        with self._lock:
            return tuple(
                self._tools[key]
                for key in sorted(self._tools)
            )


def _display(key: McpToolKey) -> str:
    return f"{key.server}:{key.name}@{key.version}"
