"""LangGraph interrupt extraction and resume-command construction."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .runtime_errors import GraphInvocationError
from .runtime_models import AgentInterrupt


INTERRUPT_KEY = "__interrupt__"


def extract_interrupts(output: Mapping[str, Any]) -> tuple[AgentInterrupt, ...]:
    """Extract LangGraph interrupts from a graph invocation result."""

    raw = output.get(INTERRUPT_KEY, ())
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raw = (raw,)

    result: list[AgentInterrupt] = []
    for index, item in enumerate(raw):
        interrupt_id = getattr(item, "id", None)
        value = getattr(item, "value", None)
        if isinstance(item, Mapping):
            interrupt_id = item.get("id", interrupt_id)
            value = item.get("value", value)
        if not isinstance(interrupt_id, str) or not interrupt_id.strip():
            raise GraphInvocationError(
                f"LangGraph interrupt at index {index} has no valid ID"
            )
        result.append(
            AgentInterrupt(
                interrupt_id=interrupt_id,
                value=value,
            )
        )
    return tuple(result)


def build_resume_payload(
    resume_value: Any,
    interrupt_id: str | None,
) -> Any:
    """Target one interrupt by ID, or resume the next interrupt."""

    if interrupt_id is None:
        return resume_value
    return {interrupt_id: resume_value}


def create_langgraph_command(
    resume_value: Any,
    interrupt_id: str | None,
) -> Any:
    """Create the official LangGraph Command lazily."""

    try:
        from langgraph.types import Command
    except ImportError as exc:
        raise GraphInvocationError(
            "LangGraph Command is unavailable"
        ) from exc
    return Command(
        resume=build_resume_payload(resume_value, interrupt_id)
    )
