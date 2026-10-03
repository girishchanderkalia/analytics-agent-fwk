"""Framework dependencies supplied to compiled LangGraph nodes.

Providers are per agent version, so the compiler builds them from the
definition rather than holding one shared set.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import Any

from bootstrap.contract_provider import create_contract_provider_for_definition
from execution.expression_evaluator import resolve_path
from langgraph_runtime.compiler import LangGraphCompiler
from langgraph_runtime.standard_nodes import (
    StandardNodeDependencies,
    StandardNodeLibrary,
)
from mcp_tools.errors import MCPServerNotFoundError, MCPToolInvocationError

COMPARISONS = ("==", "!=", ">=", "<=", ">", "<")


class ExpressionError(ValueError):
    """Raised when a declarative routing expression cannot be evaluated."""


class PackagePromptProvider:
    """Render an authored prompt together with the package's knowledge."""

    def __init__(self, definition: Any) -> None:
        self._prompts = {
            prompt.prompt_id: prompt.template for prompt in definition.prompts
        }
        self._knowledge = "\n\n".join(definition.knowledge).strip()
        self._labels = dict(getattr(definition, "knowledge_labels", None) or {})
        # Model nodes may share a prompt id, so scopes are unioned per prompt.
        self._scopes: dict[str, frozenset[str]] = {}
        for node in definition.graph.nodes:
            if node.kind != "model":
                continue
            prompt_id = node.config.get("prompt")
            if not prompt_id:
                continue
            scope = frozenset(node.config.get("knowledge_scope", ()))
            self._scopes[prompt_id] = self._scopes.get(prompt_id, frozenset()) | scope

    def render(self, prompt_id: str, state: Mapping[str, Any]) -> str:
        del state
        try:
            template = self._prompts[prompt_id]
        except KeyError as exc:
            raise ExpressionError(
                f"Agent package declares no prompt {prompt_id!r}"
            ) from exc
        sections = [template.strip()]
        if self._knowledge:
            sections.append(f"Application knowledge:\n{self._knowledge}")
        data_semantics = self._render_data_semantics(prompt_id)
        if data_semantics:
            sections.append(f"Data semantics:\n{data_semantics}")
        return "\n\n".join(sections)

    def _render_data_semantics(self, prompt_id: str) -> str:
        lines = [
            f"- {name}: {self._labels[name]['description'].strip()}"
            for name in sorted(self._scopes.get(prompt_id, frozenset()))
            if isinstance(self._labels.get(name), Mapping)
            and self._labels[name].get("description")
        ]
        return "\n".join(lines)


class TextExpressionEngine:
    """Evaluate the comparison expressions authored on routing conditions."""


    def evaluate(self, expression: str, state: Mapping[str, Any]) -> bool:
        if not isinstance(expression, str) or not expression.strip():
            raise ExpressionError("Condition must be a non-empty string")

        text = expression.strip()
        for operator in COMPARISONS:
            if operator not in text:
                continue
            left_text, right_text = text.split(operator, 1)
            left_text = left_text.strip()
            right_text = right_text.strip()
            if not left_text:
                raise ExpressionError(
                    f"Condition has no state field: {expression!r}"
                )
            left = resolve_path(state, left_text)
            right = _literal(right_text)
            return _compare(operator, left, right, expression)

        raise ExpressionError(f"Unsupported condition: {expression!r}")


class McpToolInvoker:
    """Invoke a resolved MCP tool through the framework's MCP client."""

    def __init__(
        self,
        client: Any,
        servers: Mapping[str, Any],
    ) -> None:
        self._client = client
        self._servers = dict(servers)

    def invoke(self, *, descriptor: Any, arguments: Mapping[str, Any]) -> Any:
        server_id = descriptor.key.server
        try:
            server = self._servers[server_id]
        except KeyError as exc:
            raise MCPServerNotFoundError(
                f"MCP server is not registered: {server_id}"
            ) from exc

        result = self._client.call_tool(
            server=server,
            tool_name=descriptor.key.name,
            arguments=dict(arguments),
        )

        if result.is_error:
            raise MCPToolInvocationError(
                f"MCP tool {descriptor.key.name!r} reported an error"
            )
        if result.structured_content is None:
            raise MCPToolInvocationError(
                f"MCP tool {descriptor.key.name!r} returned no structured content"
            )
        return dict(result.structured_content)


class NormalizedAgentCompiler:
    """Compile normalized definitions with per-agent node dependencies."""

    def __init__(
        self,
        *,
        model_provider: Any,
        tool_registry: Any,
        tool_invoker: Any,
        expression_engine: Any | None = None,
        interrupt_function: Any | None = None,
    ) -> None:
        self.model_provider = model_provider
        self.tool_registry = tool_registry
        self.tool_invoker = tool_invoker
        self.expression_engine = expression_engine or TextExpressionEngine()
        self.interrupt_function = interrupt_function

    def dependencies(self, definition: Any) -> StandardNodeDependencies:
        return StandardNodeDependencies(
            model_provider=self.model_provider,
            prompt_provider=PackagePromptProvider(definition),
            contract_provider=create_contract_provider_for_definition(
                definition
            ),
            tool_registry=self.tool_registry,
            tool_invoker=self.tool_invoker,
            expression_engine=self.expression_engine,
            interrupt_function=self.interrupt_function,
        )

    def compile(
        self,
        definition: Any,
        *,
        checkpointer: Any = None,
        store: Any = None,
    ) -> Any:
        library = StandardNodeLibrary(self.dependencies(definition))
        compiler = LangGraphCompiler(
            library,
            expression_engine=self.expression_engine,
        )
        return compiler.compile(
            definition,
            checkpointer=checkpointer,
            store=store,
        )


def _literal(text: str) -> Any:
    # Conditions are authored in YAML, so accept its spelling of these values.
    yaml_literals = {
        "true": True,
        "false": False,
        "null": None,
        "none": None,
    }
    if text.lower() in yaml_literals:
        return yaml_literals[text.lower()]
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text


def _compare(operator: str, left: Any, right: Any, expression: str) -> bool:
    if operator == "==":
        return left == right
    if operator == "!=":
        return left != right
    try:
        if operator == ">=":
            return left >= right
        if operator == "<=":
            return left <= right
        if operator == ">":
            return left > right
        return left < right
    except TypeError as exc:
        raise ExpressionError(
            f"Cannot compare values in condition {expression!r}"
        ) from exc
