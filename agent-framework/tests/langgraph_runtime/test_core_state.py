"""Tests for generic LangGraph state boundaries."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


V3_ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"

if str(AGENT_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME_ROOT))

from langgraph_runtime import (  # noqa: E402
    StateValidationError,
    copy_graph_state,
    validate_graph_state,
)


def test_generic_state_accepts_application_fields() -> None:
    state = {
        "conversation_id": "conversation-1",
        "question": "Interpret the data",
        "domain_specific_value": 42,
        "application_context": {},
    }

    validate_graph_state(state)


def test_copy_graph_state_is_deep() -> None:
    source = {
        "conversation_id": "conversation-1",
        "application_context": {
            "filters": ["one"],
        },
    }

    copied = copy_graph_state(source)
    copied["application_context"]["filters"].append("two")

    assert source["application_context"] == {
        "filters": ["one"],
    }


def test_invalid_framework_field_is_rejected() -> None:
    with pytest.raises(
        StateValidationError,
        match="conversation_id",
    ):
        validate_graph_state(
            {"conversation_id": ""}
        )
