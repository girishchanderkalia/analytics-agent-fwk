"""Standard condition router."""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any, Callable
from .common import public_state, require_name
from .errors import StandardNodeExecutionError


def create_condition_router(
    *,
    dependencies: Any,
    routes: tuple[tuple[Any, str], ...],
    default_destination: str,
) -> Callable[[dict[str, Any]], str]:
    normalized = tuple((condition, require_name(destination, "route destination")) for condition, destination in routes)
    fallback = require_name(default_destination, "default_destination")
    def router(state: dict[str, Any]) -> str:
        snapshot = public_state(state)
        for condition, destination in normalized:
            try:
                if dependencies.expression_engine.evaluate(condition, snapshot):
                    return destination
            except Exception as exc:
                raise StandardNodeExecutionError("Route condition evaluation failed") from exc
        return fallback
    return router
