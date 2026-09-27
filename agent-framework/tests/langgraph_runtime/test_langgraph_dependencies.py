"""Per-agent dependencies let a translated package compile and run."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
AGENT_RUNTIME = ROOT / "agent-framework" / "agent-runtime"
if str(AGENT_RUNTIME) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME))

from bootstrap.langgraph_dependencies import (  # noqa: E402
    ExpressionError,
    McpToolInvoker,
    NormalizedAgentCompiler,
    PackagePromptProvider,
    TextExpressionEngine,
)
from definitions import translate_markdown_agent  # noqa: E402
from mcp_tools.client import MCPToolResult  # noqa: E402
from mcp_tools.errors import (  # noqa: E402
    MCPServerNotFoundError,
    MCPToolInvocationError,
)
from mcp_tools.models import (  # noqa: E402
    McpToolDescriptor,
    McpToolKey,
    MCPServerRegistration,
)
from mcp_tools.registry import McpToolRegistry  # noqa: E402

AGENT = ROOT / "agents" / "opo-monitoring"

SERVER = MCPServerRegistration(
    server_id="analytics-foundation",
    display_name="analytics-foundation",
    transport="http",
    endpoint="http://127.0.0.1:8100/mcp",
)

DESCRIPTOR = McpToolDescriptor(
    McpToolKey("query_trends", "1", "analytics-foundation"),
    "Query trends",
    {"type": "object"},
)


@pytest.fixture(scope="module")
def definition():
    return translate_markdown_agent(AGENT)


class Client:
    def __init__(self, structured=None, is_error=False):
        self.structured = structured
        self.is_error = is_error
        self.calls = []

    def call_tool(self, *, server, tool_name, arguments):
        self.calls.append((server.server_id, tool_name, arguments))
        return MCPToolResult(
            structured_content=self.structured,
            is_error=self.is_error,
        )


def test_prompt_provider_appends_package_knowledge(definition) -> None:
    rendered = PackagePromptProvider(definition).render("trend_filters", {})

    assert "Extract trend filters" in rendered
    assert "Application knowledge:" in rendered


def test_unknown_prompt_is_rejected(definition) -> None:
    with pytest.raises(ExpressionError, match="no prompt"):
        PackagePromptProvider(definition).render("missing", {})


def test_expression_engine_evaluates_authored_conditions() -> None:
    engine = TextExpressionEngine()

    assert engine.evaluate("outliers == []", {"outliers": []}) is True
    assert engine.evaluate("outliers == []", {"outliers": [1]}) is False
    assert (
        engine.evaluate(
            "investigation_approved == false",
            {"investigation_approved": False},
        )
        is True
    )


def test_unsupported_expression_is_rejected() -> None:
    with pytest.raises(ExpressionError, match="Unsupported"):
        TextExpressionEngine().evaluate("outliers", {"outliers": []})


def test_tool_invoker_returns_structured_content() -> None:
    client = Client({"series": []})
    invoker = McpToolInvoker(client, {"analytics-foundation": SERVER})

    result = invoker.invoke(descriptor=DESCRIPTOR, arguments={"filters": {}})

    assert result == {"series": []}
    assert client.calls[0][:2] == ("analytics-foundation", "query_trends")


def test_tool_invoker_rejects_unregistered_server() -> None:
    invoker = McpToolInvoker(Client({}), {})

    with pytest.raises(MCPServerNotFoundError, match="analytics-foundation"):
        invoker.invoke(descriptor=DESCRIPTOR, arguments={})


def test_tool_invoker_surfaces_tool_errors() -> None:
    invoker = McpToolInvoker(
        Client({"x": 1}, is_error=True),
        {"analytics-foundation": SERVER},
    )

    with pytest.raises(MCPToolInvocationError, match="reported an error"):
        invoker.invoke(descriptor=DESCRIPTOR, arguments={})


def compiler(definition) -> NormalizedAgentCompiler:
    registry = McpToolRegistry()
    registry.register_many(
        McpToolDescriptor(
            McpToolKey(tool.name, tool.version, tool.server),
            "",
            {"type": "object"},
        )
        for tool in definition.tools
    )
    return NormalizedAgentCompiler(
        model_provider=object(),
        tool_registry=registry,
        tool_invoker=McpToolInvoker(Client({}), {}),
    )


def test_contracts_come_from_the_authored_models(definition) -> None:
    provider = compiler(definition).dependencies(definition).contract_provider

    contract = provider.get_contract("TrendFilters")

    assert "lookback_days" in contract.model_fields


def test_every_declared_tool_resolves_for_compilation(definition) -> None:
    dependencies = compiler(definition).dependencies(definition)

    for tool in definition.tools:
        assert dependencies.tool_registry.resolve(tool).key.name == tool.name


def test_authored_package_compiles_into_a_langgraph(definition) -> None:
    pytest.importorskip("langgraph.graph")

    graph = compiler(definition).compile(definition)

    assert hasattr(graph, "invoke") or hasattr(graph, "ainvoke")
    dependencies = compiler(definition).dependencies(definition)

    for tool in definition.tools:
        assert dependencies.tool_registry.resolve(tool).key.name == tool.name


def test_model_input_is_bounded_by_declared_fields(definition) -> None:
    from definitions import NormalizedNode
    from langgraph_runtime.standard_nodes import StandardNodeLibrary

    captured = {}

    class ModelProvider:
        def invoke_structured(self, **kwargs):
            captured.update(kwargs)
            return {"ok": True}

        def get_contract(self, name):
            return name

    dependencies = compiler(definition).dependencies(definition)
    node = StandardNodeLibrary(
        type(dependencies)(
            model_provider=ModelProvider(),
            prompt_provider=dependencies.prompt_provider,
            contract_provider=dependencies.contract_provider,
            tool_registry=dependencies.tool_registry,
            tool_invoker=dependencies.tool_invoker,
            expression_engine=dependencies.expression_engine,
        )
    ).create(
        NormalizedNode(
            "summarize",
            "model",
            {
                "prompt": "findings_summary",
                "output_contract": "FindingsSummary",
                "result_key": "findings",
                "inputs": ["question", "outliers"],
            },
        )
    )

    asyncio.run(node({"question": "why", "outliers": [], "wafer_rows": [1] * 5000}))

    assert "wafer_rows" not in captured["input_text"]
    assert "question" in captured["input_text"]
