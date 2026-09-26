"""Tests for generic LangGraph runtime dependencies."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


V3_ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))

from langgraph_runtime import (  # noqa: E402
    GraphDependencies,
    LangGraphDependencyError,
)


def dependency() -> object:
    return object()


def test_dependencies_are_domain_neutral() -> None:
    dependencies = GraphDependencies(
        model_provider=dependency(),
        tool_registry=dependency(),
        contract_provider=dependency(),
        prompt_provider=dependency(),
        expression_engine=dependency(),
        security_context=dependency(),
    )

    assert dependencies.model_provider is not None
    assert dependencies.tool_registry is not None


def test_missing_dependency_is_rejected() -> None:
    with pytest.raises(
        LangGraphDependencyError,
        match="tool_registry",
    ):
        GraphDependencies(
            model_provider=dependency(),
            tool_registry=None,
            contract_provider=dependency(),
            prompt_provider=dependency(),
            expression_engine=dependency(),
            security_context=dependency(),
        )
