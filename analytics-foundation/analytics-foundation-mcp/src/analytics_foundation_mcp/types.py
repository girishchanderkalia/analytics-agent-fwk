from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class FoundationMcpTool:
    name: str
    version: str
    description: str
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    annotations: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FoundationMcpToolResult:
    structured_content: Mapping[str, Any]
    is_error: bool = False
