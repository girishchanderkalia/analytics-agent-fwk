"""Discover, index, and resolve declarative application agents."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from execution.definition_loader import AgentRepository

from .catalog_models import (
    AgentCatalogEntry,
    AgentCatalogError,
    AgentNotFoundError,
    DuplicateAgentVersionError,
)


class AgentCatalog:
    """In-memory index of validated declarative agent bundles."""

    def __init__(self, repository: AgentRepository) -> None:
        self.repository = repository
        self._entries: dict[tuple[str, str], AgentCatalogEntry] = {}
        self._versions: dict[str, set[str]] = {}

    def refresh(self) -> None:
        """Reload all discoverable agents from the repository."""

        entries: dict[tuple[str, str], AgentCatalogEntry] = {}
        versions: dict[str, set[str]] = {}

        for directory_name in self.repository.list_agent_directories():
            bundle = self.repository.load(directory_name)
            entry = self._create_entry(directory_name, bundle)
            key = (entry.agent_id, entry.version)

            if key in entries:
                existing = entries[key]
                raise DuplicateAgentVersionError(
                    "Duplicate agent version "
                    f"{entry.agent_id!r} {entry.version!r} in "
                    f"{existing.agent_directory} and "
                    f"{entry.agent_directory}"
                )

            entries[key] = entry
            versions.setdefault(entry.agent_id, set()).add(entry.version)

        self._entries = entries
        self._versions = versions

    def resolve(
        self,
        agent_id: str,
        version: str | None = None,
    ) -> AgentCatalogEntry:
        """Resolve an agent version, using the highest version by default."""

        normalized_id = self._required_text(agent_id, "agent_id")

        if not self._entries:
            self.refresh()

        if version is None:
            available = self._versions.get(normalized_id)
            if not available:
                raise AgentNotFoundError(
                    f"Agent is not available: {normalized_id}"
                )
            normalized_version = max(available, key=self._version_key)
        else:
            normalized_version = self._required_text(version, "version")

        try:
            return self._entries[(normalized_id, normalized_version)]
        except KeyError as exc:
            raise AgentNotFoundError(
                f"Agent version is not available: "
                f"{normalized_id} {normalized_version}"
            ) from exc

    def contains(self, agent_id: str, version: str | None = None) -> bool:
        """Return whether an agent or exact agent version is available."""

        if not isinstance(agent_id, str) or not agent_id.strip():
            return False

        if not self._entries:
            self.refresh()

        normalized_id = agent_id.strip()

        if version is None:
            return normalized_id in self._versions

        if not isinstance(version, str) or not version.strip():
            return False

        return (normalized_id, version.strip()) in self._entries

    def versions(self, agent_id: str) -> list[str]:
        """Return available versions in ascending semantic order."""

        normalized_id = self._required_text(agent_id, "agent_id")

        if not self._entries:
            self.refresh()

        available = self._versions.get(normalized_id)
        if not available:
            raise AgentNotFoundError(
                f"Agent is not available: {normalized_id}"
            )

        return sorted(available, key=self._version_key)

    def list(self) -> list[dict[str, str]]:
        """Return public metadata for all catalog entries."""

        if not self._entries:
            self.refresh()

        return [
            entry.as_dict()
            for _, entry in sorted(
                self._entries.items(),
                key=lambda item: (
                    item[0][0],
                    self._version_key(item[0][1]),
                ),
            )
        ]

    @staticmethod
    def _create_entry(directory_name: str, bundle: Any) -> AgentCatalogEntry:
        return AgentCatalogEntry(
            agent_id=bundle.agent_id,
            version=bundle.version,
            display_name=bundle.display_name,
            directory_name=directory_name,
            agent_directory=bundle.agent_directory,
            bundle=bundle,
        )

    @staticmethod
    def _required_text(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise AgentCatalogError(
                f"{field_name} must be a non-empty string"
            )
        return value.strip()

    @staticmethod
    def _version_key(version: str) -> tuple[Any, ...]:
        """Create a stable key for dotted numeric and textual versions."""

        parts: list[Any] = []
        for part in version.replace("-", ".").split("."):
            parts.append(int(part) if part.isdigit() else part.lower())
        return tuple(parts)
