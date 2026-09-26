"""Resolve active or exact immutable agent versions."""
from __future__ import annotations
from .errors import AgentVersionResolutionError
from .models import AgentVersionReference
from .protocols import AgentVersionRepository

class AgentVersionResolver:
    def __init__(self, repository: AgentVersionRepository) -> None:
        self.repository = repository

    def resolve(self, *, agent_id: str, requested_version: str | None = None) -> AgentVersionReference:
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise AgentVersionResolutionError("agent_id must be a non-empty string")
        try:
            result = (
                self.repository.get_version(agent_id.strip(), requested_version.strip())
                if requested_version is not None
                else self.repository.get_active(agent_id.strip())
            )
        except Exception as exc:
            raise AgentVersionResolutionError(
                f"Cannot resolve agent {agent_id!r}"
            ) from exc
        if result.agent_id != agent_id.strip():
            raise AgentVersionResolutionError("Resolved agent ID does not match request")
        if requested_version is not None and result.version != requested_version.strip():
            raise AgentVersionResolutionError("Resolved agent version does not match request")
        if not result.definition_digest:
            raise AgentVersionResolutionError("Resolved agent has no definition digest")
        return result
