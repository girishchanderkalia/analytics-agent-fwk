"""Domain-neutral declarative package models."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from .errors import AgentPackageManifestError

@dataclass(frozen=True)
class AgentPackageSources:
    graph: Path
    state: Path
    prompts: Path | None = None
    tools: Path | None = None
    knowledge: tuple[Path, ...] = ()
    documentation: tuple[Path, ...] = ()
    def runtime_sources(self):
        result=[("graph",self.graph),("state",self.state)]
        if self.prompts is not None: result.append(("prompts",self.prompts))
        if self.tools is not None: result.append(("tools",self.tools))
        result.extend((f"knowledge[{i}]",p) for i,p in enumerate(self.knowledge))
        return tuple(result)
    def all_sources(self):
        return self.runtime_sources()+tuple((f"documentation[{i}]",p) for i,p in enumerate(self.documentation))

@dataclass(frozen=True)
class AgentPackageManifest:
    agent_id: str
    version: str
    sources: AgentPackageSources
    metadata: Mapping[str, Any] = field(default_factory=dict)
    def __post_init__(self):
        object.__setattr__(self,"agent_id",_text(self.agent_id,"id"))
        object.__setattr__(self,"version",_text(self.version,"version"))
        if not isinstance(self.metadata,Mapping): raise AgentPackageManifestError("metadata must be a mapping")
        object.__setattr__(self,"metadata",dict(self.metadata))

def parse_manifest_mapping(data: object) -> AgentPackageManifest:
    if not isinstance(data,Mapping): raise AgentPackageManifestError("Agent package manifest must be a mapping")
    if data.get("kind","agent-package") != "agent-package": raise AgentPackageManifestError("kind must be 'agent-package'")
    sources=data.get("sources")
    if not isinstance(sources,Mapping): raise AgentPackageManifestError("sources must be a mapping")
    missing=sorted({"graph","state"}-set(sources))
    if missing: raise AgentPackageManifestError("Missing required source roles: "+", ".join(missing))
    allowed={"graph","state","prompts","tools","knowledge","documentation"}
    unknown=sorted(set(sources)-allowed)
    if unknown: raise AgentPackageManifestError("Unknown source roles: "+", ".join(unknown))
    return AgentPackageManifest(
        agent_id=_text(data.get("id"),"id"), version=_text(data.get("version"),"version"),
        sources=AgentPackageSources(
            graph=Path(_text(sources["graph"],"sources.graph")), state=Path(_text(sources["state"],"sources.state")),
            prompts=_optional_path(sources.get("prompts"),"sources.prompts"), tools=_optional_path(sources.get("tools"),"sources.tools"),
            knowledge=_paths(sources.get("knowledge"),"sources.knowledge"), documentation=_paths(sources.get("documentation"),"sources.documentation")),
        metadata=data.get("metadata",{}))

def _text(value,field):
    if not isinstance(value,str) or not value.strip(): raise AgentPackageManifestError(f"{field} must be a non-empty string")
    return value.strip()
def _optional_path(value,field): return None if value is None else Path(_text(value,field))
def _paths(value,field):
    if value is None:return ()
    if isinstance(value,str):value=[value]
    if not isinstance(value,list):raise AgentPackageManifestError(f"{field} must be a list")
    return tuple(Path(_text(item,field)) for item in value)
