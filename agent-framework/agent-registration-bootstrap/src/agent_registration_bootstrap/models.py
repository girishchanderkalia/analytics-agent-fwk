from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True, order=True)
class AgentIdentity:
    application_id: str
    agent_id: str
    agent_version: str

    def __post_init__(self) -> None:
        for field, value in (
            ("application_id", self.application_id),
            ("agent_id", self.agent_id),
            ("agent_version", self.agent_version),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")
            object.__setattr__(self, field, value.strip())


@dataclass(frozen=True)
class ToolRegistration:
    name: str
    server: str
    version: str
    read_only: bool
    availability: str | None = None


@dataclass(frozen=True)
class AgentRegistration:
    identity: AgentIdentity
    display_name: str
    description: str
    entrypoint: str
    package_directory: Path
    graph: Mapping[str, Any]
    state: Mapping[str, Any]
    prompts: Mapping[str, Any]
    tools: tuple[ToolRegistration, ...]
    knowledge_files: tuple[Path, ...]
    fingerprint: str
