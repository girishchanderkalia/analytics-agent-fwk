"""Tests for capability registration and governance."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest


V3_ROOT = Path(__file__).resolve().parents[1]
AGENT_RUNTIME_ROOT = V3_ROOT / "agent-framework" / "agent-runtime"

agent_runtime_path = str(AGENT_RUNTIME_ROOT)

if agent_runtime_path not in sys.path:
    sys.path.insert(0, agent_runtime_path)


from capabilities.capability_models import (  # noqa: E402
    CapabilityContext,
)
from capabilities.capability_registry import (  # noqa: E402
    CapabilityAlreadyRegisteredError,
    CapabilityApprovalError,
    CapabilityExecutionError,
    CapabilityNotFoundError,
    CapabilityPermissionError,
    CapabilityRegistry,
    InvalidCapabilityError,
)


def echo_handler(
    request: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "value": request.get("value"),
    }


def test_register_and_resolve() -> None:
    registry = CapabilityRegistry()

    created = registry.register(
        "data.echo",
        "echo",
        echo_handler,
    )

    assert registry.resolve("data.echo") is created


def test_duplicate_registration_is_rejected() -> None:
    registry = CapabilityRegistry()

    registry.register(
        "data.echo",
        "echo",
        echo_handler,
    )

    with pytest.raises(
        CapabilityAlreadyRegisteredError,
    ):
        registry.register(
            "data.echo",
            "echo",
            echo_handler,
        )


def test_replace_registration() -> None:
    registry = CapabilityRegistry()

    registry.register(
        "data.echo",
        "echo",
        echo_handler,
    )

    def replacement(
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "replacement": True,
        }

    registry.register(
        "data.echo",
        "echo",
        replacement,
        replace=True,
    )

    assert registry.invoke(
        "data.echo",
        {},
    ) == {
        "replacement": True,
    }


def test_unknown_capability_is_rejected() -> None:
    registry = CapabilityRegistry()

    with pytest.raises(
        CapabilityNotFoundError,
    ):
        registry.resolve("unknown")


def test_unregister() -> None:
    registry = CapabilityRegistry()

    registry.register(
        "data.echo",
        "echo",
        echo_handler,
    )

    registry.unregister("data.echo")

    assert not registry.contains("data.echo")


def test_names_are_sorted() -> None:
    registry = CapabilityRegistry()

    registry.register(
        "z.echo",
        "echo",
        echo_handler,
    )

    registry.register(
        "a.echo",
        "echo",
        echo_handler,
    )

    assert registry.names() == [
        "a.echo",
        "z.echo",
    ]


def test_list_returns_metadata() -> None:
    registry = CapabilityRegistry()

    registry.register(
        "data.echo",
        "echo",
        echo_handler,
        description="Echo request value.",
        owner="Test",
        required_permissions={
            "data:read",
        },
        approval_required=True,
        side_effect=True,
    )

    item = registry.list()[0]

    assert item["id"] == "data.echo"
    assert item["operation"] == "echo"
    assert item["owner"] == "Test"

    assert item["required_permissions"] == [
        "data:read"
    ]

    assert item["approval_required"] is True
    assert item["side_effect"] is True


def test_invoke() -> None:
    registry = CapabilityRegistry()

    registry.register(
        "data.echo",
        "echo",
        echo_handler,
    )

    result = registry.invoke(
        "data.echo",
        {
            "value": 42,
        },
    )

    assert result == {
        "value": 42,
    }


def test_missing_permission_is_rejected() -> None:
    registry = CapabilityRegistry()

    registry.register(
        "data.echo",
        "echo",
        echo_handler,
        required_permissions={
            "data:read",
        },
    )

    with pytest.raises(
        CapabilityPermissionError,
    ):
        registry.invoke(
            "data.echo",
            {},
            context=CapabilityContext(),
        )


def test_permission_allows_invocation() -> None:
    registry = CapabilityRegistry()

    registry.register(
        "data.echo",
        "echo",
        echo_handler,
        required_permissions={
            "data:read",
        },
    )

    context = CapabilityContext.create(
        permissions={
            "data:read",
        },
    )

    result = registry.invoke(
        "data.echo",
        {},
        context=context,
    )

    assert result == {
        "value": None,
    }


def test_missing_approval_is_rejected() -> None:
    registry = CapabilityRegistry()

    registry.register(
        "workspace.create",
        "create_workspace",
        echo_handler,
        approval_required=True,
    )

    with pytest.raises(
        CapabilityApprovalError,
    ):
        registry.invoke(
            "workspace.create",
            {},
        )


def test_approval_allows_invocation() -> None:
    registry = CapabilityRegistry()

    registry.register(
        "workspace.create",
        "create_workspace",
        echo_handler,
        approval_required=True,
    )

    context = CapabilityContext(
        approved=True,
    )

    result = registry.invoke(
        "workspace.create",
        {},
        context=context,
    )

    assert result == {
        "value": None,
    }


def test_non_mapping_request_is_rejected() -> None:
    registry = CapabilityRegistry()

    registry.register(
        "data.echo",
        "echo",
        echo_handler,
    )

    with pytest.raises(
        InvalidCapabilityError,
        match="request must be a mapping",
    ):
        registry.invoke(
            "data.echo",
            ["invalid"],  # type: ignore[arg-type]
        )


def test_handler_failure_is_wrapped() -> None:
    registry = CapabilityRegistry()

    def failing(
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        raise RuntimeError("failure")

    registry.register(
        "data.fail",
        "fail",
        failing,
    )

    with pytest.raises(
        CapabilityExecutionError,
        match="failure",
    ):
        registry.invoke(
            "data.fail",
            {},
        )


def test_handler_must_return_dictionary() -> None:
    registry = CapabilityRegistry()

    def invalid(
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        return []  # type: ignore[return-value]

    registry.register(
        "data.invalid",
        "invalid",
        invalid,
    )

    with pytest.raises(
        InvalidCapabilityError,
        match="return a dictionary",
    ):
        registry.invoke(
            "data.invalid",
            {},
        )


def test_request_cannot_mutate_original() -> None:
    registry = CapabilityRegistry()

    original = {
        "nested": {
            "value": 1,
        }
    }

    def mutate(
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        request["nested"]["value"] = 2
        return {
            "done": True,
        }

    registry.register(
        "data.mutate",
        "mutate",
        mutate,
    )

    registry.invoke(
        "data.mutate",
        original,
    )

    assert original == {
        "nested": {
            "value": 1,
        }
    }


def test_non_callable_handler_is_rejected() -> None:
    registry = CapabilityRegistry()

    with pytest.raises(
        InvalidCapabilityError,
        match="callable",
    ):
        registry.register(
            "data.invalid",
            "invalid",
            "invalid",  # type: ignore[arg-type]
        )


def test_async_handler_is_rejected() -> None:
    registry = CapabilityRegistry()

    async def async_handler(
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {}

    with pytest.raises(
        InvalidCapabilityError,
        match="asynchronous",
    ):
        registry.register(
            "data.async",
            "async",
            async_handler,
        )


def test_string_permissions_are_rejected() -> None:
    registry = CapabilityRegistry()

    with pytest.raises(
        InvalidCapabilityError,
        match="collection of strings",
    ):
        registry.register(
            "data.echo",
            "echo",
            echo_handler,
            required_permissions="data:read",
        )