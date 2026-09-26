"""LangGraph installation checks kept separate from package import."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .errors import LangGraphDependencyError


def require_langgraph() -> Any:
    """Return the installed LangGraph graph module or raise a clear error."""

    try:
        return import_module("langgraph.graph")
    except ModuleNotFoundError as exc:
        raise LangGraphDependencyError(
            "LangGraph is not installed. Install dependencies from "
            "agent-framework/agent-runtime/requirements-langgraph.txt"
        ) from exc
