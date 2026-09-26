"""Domain-neutral normalized definitions consumed by the LangGraph compiler."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from mcp_tools import AgentToolReference


@dataclass(frozen=True)
class NormalizedNode:
    """One graph node without application-domain assumptions."""

    node_id: str
    kind: str
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedEdge:
    """One fixed or conditional graph transition."""

    source: str
    target: str
    condition: str | None = None


@dataclass(frozen=True)
class NormalizedGraph:
    """Graph topology ready for later LangGraph compilation."""

    entry_node: str
    nodes: tuple[NormalizedNode, ...]
    edges: tuple[NormalizedEdge, ...]


@dataclass(frozen=True)
class NormalizedState:
    """Application state schema retained as JSON-Schema-compatible data."""

    schema: Mapping[str, Any]


@dataclass(frozen=True)
class NormalizedPrompt:
    """Named prompt content and optional prompt metadata."""

    prompt_id: str
    template: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedAgentDefinition:
    """Complete domain-neutral input to later compiler slices."""

    agent_id: str
    version: str
    graph: NormalizedGraph
    state: NormalizedState
    prompts: tuple[NormalizedPrompt, ...] = ()
    tools: tuple[AgentToolReference, ...] = ()
    knowledge: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
