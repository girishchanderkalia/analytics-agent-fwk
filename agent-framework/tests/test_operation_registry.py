"""Tests for deterministic application operation registration."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

import pytest


V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"

agent_runtime_path = str(AGENT_RUNTIME_ROOT)

if agent_runtime_path not in sys.path:
    sys.path.insert(0, agent_runtime_path)


from execution.operation_registry import (  # noqa: E402
    InvalidOperationError,
    OperationAlreadyRegisteredError,
    OperationExecutionError,
    OperationNotFoundError,
    OperationRegistry,
)


def echo_operation(
    state: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "output": state.get("input"),
    }


def test_registers_operation() -> None:
    registry = OperationRegistry()

    definition = registry.register(
        name="echo",
        handler=echo_operation,
        description="Copies input into output.",
        owner="Test application",
        version="1.0",
    )

    assert definition.name == "echo"
    assert definition.description == (
        "Copies input into output."
    )
    assert definition.owner == "Test application"
    assert definition.version == "1.0"
    assert registry.contains("echo")


def test_resolves_registered_operation() -> None:
    registry = OperationRegistry()

    registered = registry.register(
        name="echo",
        handler=echo_operation,
    )

    resolved = registry.resolve("echo")

    assert resolved is registered
    assert resolved.handler is echo_operation


def test_invokes_registered_operation() -> None:
    registry = OperationRegistry()

    registry.register(
        name="echo",
        handler=echo_operation,
    )

    result = registry.invoke(
        "echo",
        {
            "input": "value",
        },
    )

    assert result == {
        "output": "value",
    }


def test_unknown_operation_is_rejected() -> None:
    registry = OperationRegistry()

    with pytest.raises(
        OperationNotFoundError,
        match="not registered",
    ):
        registry.resolve("unknown")


def test_unknown_operation_invocation_is_rejected() -> None:
    registry = OperationRegistry()

    with pytest.raises(
        OperationNotFoundError,
        match="not registered",
    ):
        registry.invoke(
            "unknown",
            {},
        )


def test_duplicate_registration_is_rejected() -> None:
    registry = OperationRegistry()

    registry.register(
        name="echo",
        handler=echo_operation,
    )

    with pytest.raises(
        OperationAlreadyRegisteredError,
        match="already registered",
    ):
        registry.register(
            name="echo",
            handler=echo_operation,
        )


def test_registration_can_replace_existing_operation() -> None:
    registry = OperationRegistry()

    def first_handler(
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "handler": "first",
        }

    def second_handler(
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "handler": "second",
        }

    registry.register(
        name="replaceable",
        handler=first_handler,
    )

    registry.register(
        name="replaceable",
        handler=second_handler,
        replace=True,
    )

    result = registry.invoke(
        "replaceable",
        {},
    )

    assert result == {
        "handler": "second",
    }


def test_unregisters_operation() -> None:
    registry = OperationRegistry()

    registered = registry.register(
        name="echo",
        handler=echo_operation,
    )

    removed = registry.unregister("echo")

    assert removed is registered
    assert not registry.contains("echo")


def test_unregistering_unknown_operation_is_rejected() -> None:
    registry = OperationRegistry()

    with pytest.raises(
        OperationNotFoundError,
        match="not registered",
    ):
        registry.unregister("unknown")


def test_names_are_sorted() -> None:
    registry = OperationRegistry()

    registry.register(
        name="second",
        handler=echo_operation,
    )

    registry.register(
        name="first",
        handler=echo_operation,
    )

    assert registry.names() == [
        "first",
        "second",
    ]


def test_list_returns_public_metadata() -> None:
    registry = OperationRegistry()

    registry.register(
        name="echo",
        handler=echo_operation,
        description="Echo input.",
        owner="Test owner",
        version="2.0",
    )

    assert registry.list() == [
        {
            "name": "echo",
            "description": "Echo input.",
            "owner": "Test owner",
            "version": "2.0",
        }
    ]


def test_operation_decorator_registers_handler() -> None:
    registry = OperationRegistry()

    @registry.operation(
        name="decorated",
        description="Registered by decorator.",
    )
    def decorated_operation(
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "decorated": True,
        }

    definition = registry.resolve("decorated")

    assert definition.handler is decorated_operation

    assert registry.invoke(
        "decorated",
        {},
    ) == {
        "decorated": True  }


def test_empty_operation_name_is_rejected() -> None:
    registry = OperationRegistry()

    with pytest.raises(
        InvalidOperationError,
        match="must not be empty",
    ):
        registry.register(
            name="  ",
            handler=echo_operation,
        )


def test_non_callable_handler_is_rejected() -> None:
    registry = OperationRegistry()

    with pytest.raises(
        InvalidOperationError,
        match="must be callable",
    ):
        registry.register(
            name="invalid",
            handler="not callable",  # type: ignore[arg-type]
        )


def test_async_handler_is_rejected() -> None:
    registry = OperationRegistry()

    async def async_handler(
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {}

    with pytest.raises(
        InvalidOperationError,
        match="asynchronous",
    ):
        registry.register(
            name="async-operation",
            handler=async_handler,
        )


def test_operation_must_return_dictionary() -> None:
    registry = OperationRegistry()

    def invalid_handler(
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        return ["not", "a", "dictionary"]  # type: ignore[return-value]

    registry.register(
        name="invalid-result",
        handler=invalid_handler,
    )

    with pytest.raises(
        InvalidOperationError,
        match="must return a dictionary",
    ):
        registry.invoke(
            "invalid-result",
            {},
        )


def test_operation_result_keys_must_be_strings() -> None:
    registry = OperationRegistry()

    def invalid_handler(
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            1: "invalid",
        }  # type: ignore[dict-item]

    registry.register(
        name="invalid-result-key",
        handler=invalid_handler,
    )

    with pytest.raises(
        InvalidOperationError,
        match="non-string field name",
    ):
        registry.invoke(
            "invalid-result-key",
            {},
        )


def test_handler_failure_is_wrapped() -> None:
    registry = OperationRegistry()

    def failing_handler(
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        raise RuntimeError("unexpected failure")

    registry.register(
        name="failing-operation",
        handler=failing_handler,
    )

    with pytest.raises(
        OperationExecutionError,
        match="unexpected failure",
    ) as error:
        registry.invoke(
            "failing-operation",
            {},
        )

    assert isinstance(
        error.value.__cause__,
        RuntimeError,
    )


def test_workflow_state_top_level_is_read_only() -> None:
    registry = OperationRegistry()

    def mutating_handler(
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        state["new_field"] = "not allowed"  # type: ignore[index]
        return {}

    registry.register(
        name="mutating-operation",
        handler=mutating_handler,
    )

    with pytest.raises(
        OperationExecutionError,
        match="does not support item assignment",
    ):
        registry.invoke(
            "mutating-operation",
            {},
        )


def test_original_nested_state_is_protected() -> None:
    registry = OperationRegistry()

    original_state = {
        "filters": {
            "lot_ids": [
                "LOT-1",
            ]
        }
    }

    def nested_mutation(
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        state["filters"]["lot_ids"].append("LOT-2")
        return {
            "count": len(
                state["filters"]["lot_ids"]
            )
        }

    registry.register(
        name="nested-mutation",
        handler=nested_mutation,
    )

    result = registry.invoke(
        "nested-mutation",
        original_state,
    )

    assert result == {
        "count": 2,
    }

    assert original_state == {
        "filters": {
            "lot_ids": [
                "LOT-1",
            ]
        }
    }


def test_returned_result_is_copied() -> None:
    registry = OperationRegistry()

    handler_result = {
        "analysis": [
            {
                "value": 1,
            }
        ]
    }

    def result_handler(
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        return handler_result

    registry.register(
        name="result-copy",
        handler=result_handler,
    )

    invocation_result = registry.invoke(
        "result-copy",
        {},
    )

    invocation_result["analysis"][0]["value"] = 99

    assert handler_result == {
        "analysis": [
            {
                "value": 1,
            }
        ]
    }


def test_non_mapping_state_is_rejected() -> None:
    registry = OperationRegistry()

    registry.register(
        name="echo",
        handler=echo_operation,
    )

    with pytest.raises(
        InvalidOperationError,
        match="state must be a mapping",
    ):
        registry.invoke(
            "echo",
            ["not", "a", "mapping"],  # type: ignore[arg-type]
        )