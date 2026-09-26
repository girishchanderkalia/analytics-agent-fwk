"""Compile declarative graph edges into LangGraph routing functions."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any

from definitions import NormalizedEdge

from .compiler_errors import GraphCompilerError


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def create_conditional_router(
    edges: tuple[NormalizedEdge, ...],
    expression_engine: Any,
):
    """Create an ordered router with exactly one declarative default edge."""

    conditional = tuple(edge for edge in edges if edge.condition is not None)
    defaults = tuple(edge for edge in edges if edge.condition is None)

    if len(defaults) != 1:
        raise GraphCompilerError(
            "Conditional routing requires exactly one default edge"
        )
    if not conditional:
        raise GraphCompilerError(
            "Conditional router requires at least one conditioned edge"
        )
    if expression_engine is None:
        raise GraphCompilerError(
            "Conditional routing requires an expression engine"
        )

    default_target = defaults[0].target

    async def route(state: Mapping[str, Any]) -> str:
        for edge in conditional:
            matched = await maybe_await(
                expression_engine.evaluate(edge.condition, state)
            )
            if not isinstance(matched, bool):
                raise GraphCompilerError(
                    "Expression engine must return a boolean"
                )
            if matched:
                return edge.target
        return default_target

    return route
