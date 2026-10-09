"""Reusable domain-neutral node factories for LangGraph workflows."""

from __future__ import annotations

import inspect
import json
import logging
import re
from time import perf_counter
from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from definitions import NormalizedNode
from execution.output_rules import check_output, normalize_output
from mcp_tools import AgentToolReference

from .node_dependencies import StandardNodeDependencies
from .node_errors import (
    NodeConfigurationError,
    NodeExecutionError,
    UnsupportedNodeKindError,
)


NodeCallable = Callable[[dict[str, Any]], Any]
logger = logging.getLogger(__name__)


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
        model_cache: dict[str, tuple[float, Any]] = {}
        configured_tools = definition.config.get("tools", [])
        tools = []
        if configured_tools:
            registry = self.dependencies.require("tool_registry")
            invoker = self.dependencies.require("tool_invoker")
            for tool in configured_tools:
                descriptor = registry.resolve(AgentToolReference(
                    name=tool["name"], version=tool["version"], server=tool["server"]
                ))
                tools.append((descriptor, tool["arguments"]))

        async def model_node(state: dict[str, Any]) -> dict[str, Any]:
            started = perf_counter()
            conversation_id = state.get("conversation_id", "unknown")
            try:
                prompt = await _maybe_await(
                    prompt_provider.render(prompt_id, state)
                )
                contract = await _maybe_await(
                    contract_provider.get_contract(output_contract)
                )
                request = {
                    "system_prompt": prompt,
                    "input_text": _model_input(definition.config, state),
                    "output_contract": contract,
                }
                logger.warning(
                    "chat_model_request_size conversation_id=%s node_id=%s system_prompt_chars=%d input_chars=%d",
                    conversation_id,
                    definition.node_id,
                    len(request["system_prompt"]),
                    len(request["input_text"]),
                )
                cache_key = None
                if definition.config.get("cacheable") and not tools:
                    cache_key = json.dumps(
                        [
                            request["system_prompt"],
                            request["input_text"],
                            output_contract,
                        ],
                        sort_keys=True,
                        default=str,
                    )
                    cached = model_cache.get(cache_key)
                    if cached is not None:
                        cached_at, cached_result = cached
                        ttl = definition.config["cache_ttl_seconds"]
                        if perf_counter() - cached_at <= ttl:
                            logger.info(
                                "chat_model_cache_hit conversation_id=%s node_id=%s",
                                conversation_id,
                                definition.node_id,
                            )
                            return {result_key: deepcopy(cached_result)}
                        model_cache.pop(cache_key, None)
                if tools:
                    call_count = 0
                    model_tools = []
                    tool_evidence = []
                    for descriptor, arguments in tools:
                        expected = _resolve_value(arguments, state)

                        async def call_tool(
                            _descriptor=descriptor, _expected=expected, **kwargs: Any
                        ) -> Any:
                            nonlocal call_count
                            tool_started = perf_counter()
                            call_count += 1
                            if call_count > definition.config["max_tool_calls"]:
                                return {"error": "Model tool call limit exceeded"}
                            approval_state = definition.config.get("approval_state")
                            if approval_state is not None and not state.get(approval_state):
                                return {"error": "Approval required before this tool call"}
                            if any(key not in _expected or _expected[key] != value for key, value in kwargs.items()):
                                return {"error": "Tool filters differ from established trend filters"}
                            try:
                                evidence = await _maybe_await(invoker.invoke(
                                    descriptor=_descriptor, arguments=_expected
                                ))
                                tool_evidence.append(evidence)
                                logger.warning(
                                    "chat_tool_complete conversation_id=%s node_id=%s tool=%s elapsed_ms=%d",
                                    conversation_id,
                                    definition.node_id,
                                    _descriptor.key.name,
                                    (perf_counter() - tool_started) * 1000,
                                )
                                return evidence
                            except Exception:
                                logger.exception(
                                    "chat_tool_failed conversation_id=%s node_id=%s tool=%s elapsed_ms=%d",
                                    conversation_id,
                                    definition.node_id,
                                    _descriptor.key.name,
                                    (perf_counter() - tool_started) * 1000,
                                )
                                return {"error": "Model tool unavailable"}

                        model_tools.append({
                            "name": tool.get("model_name", descriptor.key.name),
                            "description": descriptor.description,
                            "json_schema": descriptor.input_schema,
                            "function": call_tool,
                        })
                    request["tools"] = model_tools
                model_started = perf_counter()
                result = await _maybe_await(model_provider.invoke_structured(**request))
                logger.warning(
                    "chat_model_provider_complete conversation_id=%s node_id=%s elapsed_ms=%d",
                    conversation_id,
                    definition.node_id,
                    (perf_counter() - model_started) * 1000,
                )
                logger.info(
                    "chat_model_complete conversation_id=%s node_id=%s elapsed_ms=%d",
                    conversation_id,
                    definition.node_id,
                    (perf_counter() - started) * 1000,
                )
                if tools and definition.config.get("require_tool_call") and not tool_evidence:
                    raise NodeExecutionError(
                        f"Model node {definition.node_id!r} returned without calling its required tool"
                    )
                if hasattr(result, "model_dump"):
                    result = result.model_dump(mode="python")
                logger.warning(
                    "chat_model_response_size conversation_id=%s node_id=%s output_chars=%d tool_calls=%d",
                    conversation_id,
                    definition.node_id,
                    len(json.dumps(result, default=str)),
                    call_count if tools else 0,
                )
                if cache_key is not None:
                    model_cache[cache_key] = (perf_counter(), deepcopy(result))
                    logger.warning(
                        "chat_model_cache_store conversation_id=%s node_id=%s",
                        conversation_id,
                        definition.node_id,
                    )
                for field, sources in definition.config.get("grounded_outputs", {}).items():
                    value = result.get(field)
                    if value is not None and not any(
                        isinstance(evidence, Mapping)
                        and evidence.get("sample_count") != 0
                        and value == evidence.get(source)
                        for evidence in tool_evidence for source in sources
                    ):
                        raise NodeExecutionError(
                            f"Model output {field!r} is not grounded in tool evidence"
                        )
            except Exception as exc:
                logger.exception(
                    "chat_model_failed conversation_id=%s node_id=%s elapsed_ms=%d",
                    conversation_id,
                    definition.node_id,
                    (perf_counter() - started) * 1000,
                )
                raise NodeExecutionError(
                    f"Model node {definition.node_id!r} failed"
                ) from exc
            guardrails = definition.config.get("guardrails")
            if not guardrails:
                output = {result_key: result}
                if tools and definition.config.get("tool_results_to"):
                    output[definition.config["tool_results_to"]] = (
                        tool_evidence[0] if len(tool_evidence) == 1 else tool_evidence
                    )
                return output
            output = await _apply_guardrails(
                definition.node_id, guardrails, result_key, result, request, state, model_provider
            )
            if tools and definition.config.get("tool_results_to"):
                output[definition.config["tool_results_to"]] = (
                    tool_evidence[0] if len(tool_evidence) == 1 else tool_evidence
                )
            return output

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
        approval_id = definition.config.get("approval_id")

        async def interrupt_node(state: dict[str, Any]) -> dict[str, Any]:
            resolved_payload = _resolve_value(payload, state)
            if isinstance(approval_id, str) and approval_id.strip():
                resolved_payload = {
                    "type": "approval_required",
                    "approval_id": approval_id.strip(),
                    "payload": resolved_payload,
                }
            decision = interrupt_function(resolved_payload)
            decision = await _maybe_await(decision)
            updates = {result_key: decision}
            decision_fields = definition.config.get("decision_fields", {})
            if isinstance(decision_fields, Mapping) and isinstance(decision, Mapping):
                for field, decision_key in decision_fields.items():
                    if not isinstance(field, str) or not isinstance(decision_key, str):
                        continue
                    value = decision.get(decision_key)
                    if field == "selected_outlier" and isinstance(value, str):
                        candidates = state.get(
                            definition.config.get("selection_from", "outliers"),
                            [],
                        )
                        value = next(
                            (
                                item for index, item in enumerate(candidates)
                                if isinstance(item, Mapping)
                                and (
                                    item.get("id") == value
                                    or str(index) == value
                                )
                            ),
                            None,
                        )
                    updates[field] = value
            return updates

        return interrupt_node


async def _apply_guardrails(
    node_id: str,
    guardrails: Mapping[str, Any],
    result_key: str,
    result: Any,
    request: dict[str, Any],
    state: Mapping[str, Any],
    model_provider: Any,
) -> dict[str, Any]:
    """Check declared rules, re-ask the model with the violations, and report the outcome."""

    first = check_output(result, guardrails["rules"], state)
    result = normalize_output(result, guardrails["rules"], state)
    violations = check_output(result, guardrails["rules"], state)
    attempts = 1
    while violations and attempts <= guardrails["retries"]:
        correction = dict(request)
        correction["input_text"] = (
            f"{request['input_text']}\n\nYour previous answer was:\n{json.dumps(result, default=str)}\n"
            "It violates these rules:\n" + "\n".join(f"- {item}" for item in violations)
            + "\nReturn a corrected answer that satisfies every rule."
        )
        try:
            result = await _maybe_await(model_provider.invoke_structured(**correction))
            if hasattr(result, "model_dump"):
                result = result.model_dump(mode="python")
        except Exception as exc:
            raise NodeExecutionError(f"Model node {node_id!r} failed on guardrail retry") from exc
        result = normalize_output(result, guardrails["rules"], state)
        violations = check_output(result, guardrails["rules"], state)
        attempts += 1

    status = "failed" if violations else ("corrected" if first else "passed")
    if status == "failed" and guardrails["on_failure"] == "stop":
        raise NodeExecutionError(f"Model node {node_id!r} violates its guardrails: {violations}")
    report = dict(state.get(guardrails["report_to"]) or {})
    report[node_id] = {"status": status, "attempts": attempts, "violations": violations, "corrected": first if status == "corrected" else []}
    return {result_key: result, guardrails["report_to"]: report}


def _model_input(config: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    # A node may declare the state it needs: evidence collections can be far
    # larger than a model context window.
    projection = config.get("input_projection")
    if isinstance(projection, Mapping) and projection:
        return str(_resolve_input_projection(projection, state))
    fields = config.get("inputs")
    if isinstance(fields, list) and fields:
        return str(
            {
                name: state[name]
                for name in fields
                if isinstance(name, str) and name in state
            }
        )
    input_path = config.get("input")
    if input_path is None:
        return str(state.get("messages", state))
    value = _resolve_value(input_path, state)
    return value if isinstance(value, str) else str(value)


def _resolve_input_projection(
    projection: Mapping[str, Any],
    state: Mapping[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in projection.items():
        if isinstance(value, Mapping) and "select_item" in value:
            source = _resolve_value(value["select_item"], state)
            where = value.get("where", {})
            if not isinstance(source, list) or not isinstance(where, Mapping) or not where:
                raise NodeExecutionError(f"Projection {key!r} requires a list and non-empty where mapping")
            matches = [item for item in source if isinstance(item, Mapping)
                       and all(item.get(field) == expected for field, expected in where.items())]
            if len(matches) != 1:
                raise NodeExecutionError(f"Projection {key!r} expected exactly one matching item, got {len(matches)}")
            fields = value.get("fields")
            result[key] = ({field: deepcopy(matches[0].get(field)) for field in fields}
                           if isinstance(fields, list) else deepcopy(matches[0]))
            continue
        if isinstance(value, Mapping) and "compact_list" in value:
            source = _resolve_value(value["compact_list"], state)
            if not isinstance(source, list):
                result[key] = []
                continue
            fields = value.get("fields", [])
            point_fields = value.get("point_fields", [])
            point_format = value.get("point_format", "object")
            result[key] = [
                {
                    field: (
                        [
                            [point.get(point_field) for point_field in point_fields]
                            if point_format == "list"
                            else {
                                point_field: point.get(point_field)
                                for point_field in point_fields
                            }
                            for point in item.get(field, [])
                            if isinstance(point, Mapping)
                        ]
                        if field == "points"
                        else item.get(field)
                    )
                    for field in fields
                    if isinstance(item, Mapping)
                }
                for item in source
            ]
            continue
        result[key] = _resolve_value(value, state)
    return result


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
        indexed = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]", segment)
        if indexed:
            key, index_text = indexed.groups()
            if not isinstance(current, Mapping) or key not in current:
                raise NodeExecutionError(f"State reference does not exist: $.{path}")
            current = current[key]
            index = int(index_text)
            if not isinstance(current, list) or index >= len(current):
                raise NodeExecutionError(f"State reference does not exist: $.{path}")
            current = current[index]
            continue
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
