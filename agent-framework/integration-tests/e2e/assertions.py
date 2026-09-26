from __future__ import annotations

from collections.abc import Mapping
from typing import Any


RUNTIME_INTERNAL_FIELDS = {
    "thread_id",
    "threadId",
    "checkpoint_id",
    "checkpointId",
    "checkpoint_ns",
    "checkpointNamespace",
    "current_node",
    "currentNode",
}


def assert_no_runtime_internals(value: Any) -> None:
    if isinstance(value, Mapping):
        forbidden = RUNTIME_INTERNAL_FIELDS.intersection(value)
        assert not forbidden, (
            "Public response leaked runtime internals: "
            + ", ".join(sorted(forbidden))
        )
        for item in value.values():
            assert_no_runtime_internals(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_runtime_internals(item)


def assert_runtime_response(value: Mapping[str, Any]) -> None:
    assert isinstance(value.get("conversationId"), str)
    assert value["conversationId"].strip()
    assert isinstance(value.get("agentId"), str)
    assert isinstance(value.get("status"), str)
    assert isinstance(value.get("version"), int)
    assert isinstance(value.get("result"), Mapping)
    assert_no_runtime_internals(value)
