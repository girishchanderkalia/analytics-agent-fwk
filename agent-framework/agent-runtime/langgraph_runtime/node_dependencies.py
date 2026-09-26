"""Explicit domain-neutral dependencies used by standard node factories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .node_errors import NodeConfigurationError


@dataclass(frozen=True)
class StandardNodeDependencies:
    """Services supplied by the framework when compiling standard nodes."""

    model_provider: Any = None
    prompt_provider: Any = None
    contract_provider: Any = None
    tool_registry: Any = None
    tool_invoker: Any = None
    expression_engine: Any = None
    interrupt_function: Any = None

    def require(self, name: str) -> Any:
        """Return one dependency or raise a configuration error."""

        value = getattr(self, name, None)
        if value is None:
            raise NodeConfigurationError(
                f"Standard node dependency is not configured: {name}"
            )
        return value
