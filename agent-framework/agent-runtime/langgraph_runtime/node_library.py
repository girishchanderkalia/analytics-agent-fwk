"""Reusable domain-neutral node factories for LangGraph workflows."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from definitions import NormalizedNode
from mcp_tools import AgentToolReference

from .node_dependencies import StandardNodeDependencies
from .node_errors import (
    NodeConfigurationError,
    NodeExecutionError,
    UnsupportedNodeKindError,
)


NodeCallable = Callable[[dict[str, Any]], Any]


class StandardNodeLibrary:
    """Create standard nodes from normalized definitions.

    Supported kinds are framework concepts only: model, tool, transform, and
    interrupt. Application-specific behavior remains in prompts, state,
    declarative configuration, knowledge, and MCP tools.
    """

    def __init__(self, dependencies: StandardNodeDependencies) -> None:
        self.dependencies = dependencies
        self._factories = {
            "model": self._create_model_node,
            "tool": self._create_tool_node,
            "transform": self._create_transform_node,
            "interrupt": self._create_interrupt_node,
        }

    @property
    def supported_kinds(self) -> frozenset[str]:
        return frozenset(self._factories)

    def create(self, definition: NormalizedNode) -> NodeCallable:
        try:
            factory = self._factories[definition.kind]
        except KeyError as exc:
            raise UnsupportedNodeKindError(
                f"Unsupported standard node kind: {definition.kind}"
            ) from exc
        return factory(definition)

    def _create_model_node(self, definition: NormalizedNode) -> NodeCallable:
        prompt_id = _required_text(definition.config, "prompt", definition.node_id)
        output_contract = _required_text(
            definition.config,
            "output_contract",
            definition.node_id,
        )
        result_key = _required_text(
            definition.config,
            "result_key",
            definition.node_id,
        )

        prompt_provider = self.dependencies.require("prompt_provider")
        contract_provider = self.dependencies.require("contract_provider")
        model_provider = self.dependencies.require("model_provider")

        async def model_node(state: dict[str, Any]) -> dict[str, Any]:
            try:
                prompt = await _maybe_await(
                    prompt_provider.render(prompt_id, state)
                )
                contract = await _maybe_await(
                    contract_provider.get_contract(output_contract)
                )
                result = await _maybe_await(
                    model_provider.invoke_structured(
                        system_prompt=prompt,
                        input_text=_model_input(definition.config, state),
                        output_contract=contract,
                    )
                )
            except Exception as exc:
                raise NodeExecutionError(
                    f"Model node {definition.node_id!r} failed"
                ) from exc
            return {result_key: result}

        return model_node

    def _create_tool_node(self, definition: NormalizedNode) -> NodeCallable:
        tool_name = _required_text(definition.config, "tool", definition.node_id)
        version = _required_text(definition.config, "version", definition.node_id)
        server = definition.config.get("server")
        if server is not None and (not isinstance(server, str) or not server.strip()):
            raise NodeConfigurationError(
                f"Node {definition.node_id!r} config 'server' must be a string"
            )
        result_key = _required_text(
            definition.config,
            "result_key",
            definition.node_id,
        )
        arguments = definition.config.get("arguments", {})
        if not isinstance(arguments, Mapping):
            raise NodeConfigurationError(
                f"Node {definition.node_id!r} config 'arguments' must be a mapping"
            )

        registry = self.dependencies.require("tool_registry")
        invoker = self.dependencies.require("tool_invoker")
        descriptor = registry.resolve(
            AgentToolReference(
                name=tool_name,
                version=version,
                server=None if server is None else server.strip(),
            )
        )

        async def tool_node(state: dict[str, Any]) -> dict[str, Any]:
            resolved_arguments = _resolve_value(arguments, state)
            try:
                result = await _maybe_await(
                    invoker.invoke(
                        descriptor=descriptor,
                        arguments=resolved_arguments,
                    )
                )
            except Exception as exc:
                raise NodeExecutionError(
                    f"Tool node {definition.node_id!r} failed"
                ) from exc
            return {result_key: result}

        return tool_node

    def _create_transform_node(self, definition: NormalizedNode) -> NodeCallable:
        assignments = definition.config.get("assignments")
        if not isinstance(assignments, Mapping) or not assignments:
            raise NodeConfigurationError(
                f"Node {definition.node_id!r} requires non-empty assignments"
            )

        async def transform_node(state: dict[str, Any]) -> dict[str, Any]:
            return {
                target: _resolve_value(source, state)
                for target, source in assignments.items()
            }

        return transform_node

    def _create_interrupt_node(self, definition: NormalizedNode) -> NodeCallable:
        payload = definition.config.get("payload", {})
        if not isinstance(payload, Mapping):
            raise NodeConfigurationError(
                f"Node {definition.node_id!r} config 'payload' must be a mapping"
            )
        result_key = _required_text(
            definition.config,
            "result_key",
            definition.node_id,
        )
        interrupt_function = (
            self.dependencies.interrupt_function
            or _langgraph_interrupt
        )

        async def interrupt_node(state: dict[str, Any]) -> dict[str, Any]:
            resolved_payload = _resolve_value(payload, state)
            decision = interrupt_function(resolved_payload)
            decision = await _maybe_await(decision)
            return {result_key: decision}

        return interrupt_node


def _model_input(config: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    input_path = config.get("input")
    if input_path is None:
        return str(state.get("messages", state))
    value = _resolve_value(input_path, state)
    return value if isinstance(value, str) else str(value)


def _resolve_value(value: Any, state: Mapping[str, Any]) -> Any:
    """Resolve `$` state references in declarative node configuration."""

    if isinstance(value, str) and value.startswith("$."):
        return deepcopy(_read_path(state, value[2:]))
    if isinstance(value, Mapping):
        return {
            key: _resolve_value(item, state)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_resolve_value(item, state) for item in value]
    if isinstance(value, tuple):
        return tuple(_resolve_value(item, state) for item in value)
    return deepcopy(value)


def _read_path(state: Mapping[str, Any], path: str) -> Any:
    current: Any = state
    for segment in path.split("."):
        if not segment:
            raise NodeExecutionError(f"Invalid state reference: $.{path}")
        if not isinstance(current, Mapping) or segment not in current:
            raise NodeExecutionError(f"State reference does not exist: $.{path}")
        current = current[segment]
    return current


def _required_text(
    config: Mapping[str, Any],
    key: str,
    node_id: str,
) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise NodeConfigurationError(
            f"Node {node_id!r} requires non-empty config {key!r}"
        )
    return value.strip()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _langgraph_interrupt(payload: Mapping[str, Any]) -> Any:
    try:
        from langgraph.types import interrupt
    except ImportError as exc:
        raise NodeExecutionError(
            "LangGraph interrupt is unavailable"
        ) from exc
    return interrupt(payload)
