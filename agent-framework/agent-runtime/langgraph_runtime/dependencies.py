"""Generic dependencies supplied to compiled LangGraph nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import LangGraphDependencyError


@dataclass(frozen=True)
class GraphDependencies:
    """Runtime services available to generic nodes.

    The fields intentionally contain no application-domain concepts. Concrete
    protocols will be introduced in the later model, MCP tool, prompt, and
    expression slices without changing the graph's central ownership.
    """

    model_provider: Any
    tool_registry: Any
    contract_provider: Any
    prompt_provider: Any
    expression_engine: Any
    security_context: Any

    def __post_init__(self) -> None:
        required = {
            "model_provider": self.model_provider,
            "tool_registry": self.tool_registry,
            "contract_provider": self.contract_provider,
            "prompt_provider": self.prompt_provider,
            "expression_engine": self.expression_engine,
            "security_context": self.security_context,
        }

        missing = [
            name
            for name, value in required.items()
            if value is None
        ]

        if missing:
            raise LangGraphDependencyError(
                "Missing LangGraph runtime dependencies: "
                + ", ".join(sorted(missing))
            )
