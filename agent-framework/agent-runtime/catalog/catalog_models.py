"""Models used by the declarative agent catalog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AgentCatalogError(ValueError):
    """Base error raised by the Agent Catalog."""


class AgentNotFoundError(AgentCatalogError):
    """Raised when an agent ID or version cannot be resolved."""


class DuplicateAgentVersionError(AgentCatalogError):
    """Raised when the same agent ID and version occur more than once."""


@dataclass(frozen=True)
class AgentCatalogEntry:
    """One validated agent version available to the runtime."""

    agent_id: str
    version: str
    display_name: str
    directory_name: str
    agent_directory: Path
    bundle: Any

    def as_dict(self) -> dict[str, str]:
        """Return public catalog metadata."""

        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "display_name": self.display_name,
            "directory_name": self.directory_name,
            "agent_directory": str(self.agent_directory),
        }
