from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent-framework" / "agent-runtime"))

from definitions import NormalizedNode
from langgraph_runtime.standard_nodes import (
    NodeConfigurationError,
    NodeExecutionError,
    StandardNodeDependencies,
    StandardNodeLibrary,
    UnsupportedNodeKindError,
)
from mcp_tools import McpToolDescriptor, McpToolKey, McpToolRegistry


class PromptProvider:
    def render(self, prompt_id, state):
        return f"{prompt_id}:{state['question']}"


class ContractProvider:
    def get_contract(self, name):
        return {"contract": name}


class ModelProvider:
    def invoke_structured(self, **kwargs):
        return kwargs


class ToolInvoker:
    async def invoke(self, *, descriptor, arguments):
        return {"tool": descriptor.key.name, "arguments": arguments}


def dependencies(**changes):
    values = {
        "model_provider": ModelProvider(),
        "prompt_provider": PromptProvider(),
        "contract_provider": ContractProvider(),
        "tool_registry": McpToolRegistry(),
        "tool_invoker": ToolInvoker(),
        "interrupt_function": lambda payload: {"decision": payload},
    }
    values.update(changes)
    return StandardNodeDependencies(**values)


def run(node, state):
    return asyncio.run(node(state))


def test_model_node_uses_generic_providers() -> None:
    node = StandardNodeLibrary(dependencies()).create(
        NormalizedNode(
            "interpret",
            "model",
            {
                "prompt": "interpret-request",
                "output_contract": "Interpretation",
                "result_key": "interpretation",
                "input": "$.question",
            },
        )
    )
    result = run(node, {"question": "Explain"})
    assert result["interpretation"]["input_text"] == "Explain"
    assert result["interpretation"]["system_prompt"] == "interpret-request:Explain"


def test_cacheable_model_node_reuses_result_for_same_input() -> None:
    class CountingModel:
        def __init__(self):
            self.calls = 0

        def invoke_structured(self, **kwargs):
            self.calls += 1
            return {"call": self.calls, "input": kwargs["input_text"]}

    model = CountingModel()
    node = StandardNodeLibrary(dependencies(model_provider=model)).create(
        NormalizedNode(
            "interpret",
            "model",
            {
                "prompt": "interpret-request",
                "output_contract": "Interpretation",
                "result_key": "interpretation",
                "input": "$.question",
                "cacheable": True,
                "cache_ttl_seconds": 60,
            },
        )
    )

    first = run(node, {"question": "Explain", "conversation_id": "one"})
    second = run(node, {"question": "Explain", "conversation_id": "two"})

    assert model.calls == 1
    assert first == second


def test_model_input_projection_omits_large_evidence_fields() -> None:
    class CapturingModel:
        def invoke_structured(self, **kwargs):
            return {"input": kwargs["input_text"]}

    node = StandardNodeLibrary(
        dependencies(model_provider=CapturingModel())
    ).create(
        NormalizedNode(
            "analyze",
            "model",
            {
                "prompt": "analysis",
                "output_contract": "Analysis",
                "result_key": "analysis",
                "input_projection": {
                    "before": {
                        "period": "$.before.period",
                        "budgets": "$.before.budgets",
                    }
                },
            },
        )
    )

    result = run(
        node,
        {
            "question": "Explain",
            "before": {
                "period": "before",
                "budgets": [{"name": "nce"}],
                "wafer_map": [{"row": "large"}],
            }
        },
    )

    assert "wafer_map" not in result["analysis"]["input"]
    assert "nce" in result["analysis"]["input"]


def test_source_selection_derives_filters_from_the_question_not_the_model() -> None:
    from execution.output_rules import check_output, normalize_output, validate_rule

    rule = {"field": "chuck_ids", "rule": "source_selection", "source": "$.question",
        "aliases": {"Waferstage chuck ID 1": r"\bchuck\s*(?:id\s*)?1\b",
            "Waferstage chuck ID 2": r"\bchuck\s*(?:id\s*)?2\b"}}
    validate_rule(rule, "test")
    output = {"chuck_ids": ["Waferstage chuck ID 1"], "product_ids": ["AAA2"]}
    state = {"question": "Show OPO performance of product AAA2, layer OV_NO_ID2 on scanner GW021 since 17 Aug."}
    assert check_output(output, [rule], state)
    normalized = normalize_output(output, [rule], state)
    assert normalized == {"chuck_ids": [], "product_ids": ["AAA2"]}
    assert check_output(normalized, [rule], state) == []
    assert output["chuck_ids"] == ["Waferstage chuck ID 1"]
    assert normalize_output(output, [rule], {"question": "scanner GW021, chuck 1"})["chuck_ids"] == ["Waferstage chuck ID 1"]
    assert normalize_output(output, [rule], {"question": "scanner GW021, chuck ID 2"})["chuck_ids"] == ["Waferstage chuck ID 2"]
    assert normalize_output(output, [rule], {"question": "both chucks since 17 Aug"})["chuck_ids"] == []
    assert normalize_output(output, [rule], {"question": "scanner GW021 on 1 Sep"})["chuck_ids"] == []


def test_model_guardrails_correct_invented_filters_before_downstream_tools() -> None:
    class InventedChuckModel:
        def invoke_structured(self, **kwargs):
            return {"chuck_ids": ["Waferstage chuck ID 1"], "product_ids": ["AAA2"]}

    node = StandardNodeLibrary(dependencies(model_provider=InventedChuckModel())).create(NormalizedNode(
        "parse", "model", {"prompt": "parse", "output_contract": "Filters", "result_key": "filters",
                           "guardrails": {"report_to": "filter_validation", "retries": 1, "on_failure": "stop", "rules": [
                               {"field": "chuck_ids", "rule": "source_selection", "source": "$.question",
                                "aliases": {"Waferstage chuck ID 1": r"\bchuck\s*(?:id\s*)?1\b",
                                            "Waferstage chuck ID 2": r"\bchuck\s*(?:id\s*)?2\b"}}]}}))
    result = run(node, {"question": "Show OPO performance of product AAA2, layer OV_NO_ID2 on scanner GW021 since 17 Aug."})
    assert result["filters"]["chuck_ids"] == []
    assert result["filters"]["product_ids"] == ["AAA2"]
    assert result["filter_validation"]["parse"]["status"] == "corrected"
    assert result["filter_validation"]["parse"]["attempts"] == 1
    explicit = run(node, {"question": "Show OPO for chuck ID 2"})
    assert explicit["filters"]["chuck_ids"] == ["Waferstage chuck ID 2"]


def test_model_projection_selects_only_the_named_period() -> None:
    from langgraph_runtime.node_library import _resolve_input_projection

    projection = {"after": {"select_item": "$.periods", "where": {"period": "after"},
                            "fields": ["period", "lot_count", "budgets"]}}
    periods = [{"period": "after", "lot_count": 60, "budgets": ["full-window"], "maps": ["large"]},
               {"period": "before", "lot_count": 30, "budgets": ["before-window"]}]
    assert _resolve_input_projection(projection, {"periods": periods}) == {
        "after": {"period": "after", "lot_count": 60, "budgets": ["full-window"]}}
    with pytest.raises(NodeExecutionError, match="exactly one"):
        _resolve_input_projection(projection, {"periods": [periods[1]]})
    with pytest.raises(NodeExecutionError, match="exactly one"):
        _resolve_input_projection(projection, {"periods": [periods[0], periods[0]]})


def test_model_input_projection_compacts_nested_points() -> None:
    class CapturingModel:
        def invoke_structured(self, **kwargs):
            return {"input": kwargs["input_text"]}

    node = StandardNodeLibrary(
        dependencies(model_provider=CapturingModel())
    ).create(
        NormalizedNode(
            "analyze",
            "model",
            {
                "prompt": "analysis",
                "output_contract": "Analysis",
                "result_key": "analysis",
                "input_projection": {
                    "series": {
                        "compact_list": "$.series",
                        "fields": ["machine", "points"],
                        "point_fields": ["date", "kpi_value"],
                        "point_format": "list",
                    }
                },
            },
        )
    )

    result = run(
        node,
        {
            "question": "Explain",
            "series": [{
                "machine": "GW021",
                "points": [{"date": "2026-01-01", "kpi_value": 1.2, "raw": "omit"}],
                "maps": [{"large": "omit"}],
            }],
        },
    )

    assert "raw" not in result["analysis"]["input"]
    assert "large" not in result["analysis"]["input"]
    assert "2026-01-01" in result["analysis"]["input"]


def test_model_tool_uses_established_filters_and_call_limit() -> None:
    deps = dependencies()
    deps.tool_registry.register_many([
        McpToolDescriptor(
            McpToolKey("get_distribution_stats", "1", "data"),
            "Read distribution statistics", {"type": "object", "properties": {"days": {"type": "integer"}}},
        )
    ])

    class CallingModel:
        async def invoke_structured(self, **kwargs):
            tool = kwargs["tools"][0]
            assert tool["json_schema"]["properties"]["days"]["type"] == "integer"
            first = await tool["function"](days=7)
            second = await tool["function"](days=7)
            return {"first": first, "second": second}

    node = StandardNodeLibrary(dependencies(
        tool_registry=deps.tool_registry,
        tool_invoker=deps.tool_invoker,
        model_provider=CallingModel(),
    )).create(NormalizedNode("scope", "model", {
        "prompt": "scope", "output_contract": "Scope", "result_key": "scope",
        "tools": [{"name": "get_distribution_stats", "version": "1", "server": "data",
                   "arguments": {"days": "$.trend_filters.lookback_days"}}],
        "max_tool_calls": 1,
    }))

    result = run(node, {"question": "outliers", "trend_filters": {"lookback_days": 7}})
    assert result["scope"]["first"]["arguments"] == {"days": 7}
    assert result["scope"]["second"] == {"error": "Model tool call limit exceeded"}


def test_model_tool_rejects_changed_filters() -> None:
    deps = dependencies()
    deps.tool_registry.register_many([
        McpToolDescriptor(McpToolKey("stats", "1", "data"), "Stats", {"type": "object"})
    ])

    class CallingModel:
        async def invoke_structured(self, **kwargs):
            return await kwargs["tools"][0]["function"](days=30)

    node = StandardNodeLibrary(dependencies(
        tool_registry=deps.tool_registry,
        tool_invoker=deps.tool_invoker,
        model_provider=CallingModel(),
    )).create(NormalizedNode("scope", "model", {
        "prompt": "scope", "output_contract": "Scope", "result_key": "scope",
        "tools": [{"name": "stats", "version": "1", "server": "data",
                   "arguments": {"days": "$.trend_filters.lookback_days"}}],
        "max_tool_calls": 1,
    }))

    assert run(node, {"question": "outliers", "trend_filters": {"lookback_days": 7}}) == {
        "scope": {"error": "Tool filters differ from established trend filters"}
    }


@pytest.mark.parametrize(
    ("stats", "suggested", "accepted"),
    [({"sample_count": 50, "p95": 3.2}, 3.2, True),
     ({"sample_count": 50, "p95": 3.2}, 4.0, False),
     ({"sample_count": 0, "p95": 3.2}, 3.2, False)],
)
def test_suggested_cutoff_must_match_tool_evidence(stats, suggested, accepted) -> None:
    deps = dependencies()
    deps.tool_registry.register_many([
        McpToolDescriptor(McpToolKey("stats", "1", "data"), "Stats", {"type": "object"})
    ])

    class StatsInvoker:
        def invoke(self, *, descriptor, arguments):
            return stats

    class CallingModel:
        async def invoke_structured(self, **kwargs):
            await kwargs["tools"][0]["function"](days=7)
            return {"suggested_limit_value": suggested}

    node = StandardNodeLibrary(dependencies(
        tool_registry=deps.tool_registry,
        tool_invoker=StatsInvoker(),
        model_provider=CallingModel(),
    )).create(NormalizedNode("scope", "model", {
        "prompt": "scope", "output_contract": "Scope", "result_key": "scope",
        "tools": [{"name": "stats", "version": "1", "server": "data",
                   "arguments": {"days": "$.trend_filters.lookback_days"}}],
        "max_tool_calls": 1,
        "grounded_outputs": {"suggested_limit_value": ["p95", "p99"]},
    }))
    state = {"question": "outliers", "trend_filters": {"lookback_days": 7}}

    if accepted:
        assert run(node, state)["scope"]["suggested_limit_value"] == suggested
    else:
        with pytest.raises(NodeExecutionError) as exc:
            run(node, state)
        assert "not grounded" in str(exc.value.__cause__)


def test_tool_node_resolves_arguments_and_invokes_mcp_tool() -> None:
    deps = dependencies()
    deps.tool_registry.register_many([
        McpToolDescriptor(
            McpToolKey("read_data", "1", "data"),
            "Read data",
            {"type": "object"},
        )
    ])
    node = StandardNodeLibrary(deps).create(
        NormalizedNode(
            "retrieve",
            "tool",
            {
                "tool": "read_data",
                "version": "1",
                "server": "data",
                "arguments": {"query": "$.filters.query"},
                "result_key": "retrieved",
            },
        )
    )
    result = run(node, {"filters": {"query": "recent"}})
    assert result == {
        "retrieved": {
            "tool": "read_data",
            "arguments": {"query": "recent"},
        }
    }


def test_transform_node_maps_state_without_domain_logic() -> None:
    node = StandardNodeLibrary(dependencies()).create(
        NormalizedNode(
            "prepare",
            "transform",
            {
                "assignments": {
                    "selected": "$.result.items",
                    "constant": True,
                }
            },
        )
    )
    result = run(node, {"result": {"items": [1, 2]}})
    assert result == {"selected": [1, 2], "constant": True}


def test_interrupt_node_uses_injected_interrupt_function() -> None:
    node = StandardNodeLibrary(dependencies()).create(
        NormalizedNode(
            "approval",
            "interrupt",
            {
                "payload": {"candidate": "$.candidate"},
                "result_key": "approval",
            },
        )
    )
    result = run(node, {"candidate": "item-1"})
    assert result == {
        "approval": {
            "decision": {"candidate": "item-1"},
        }
    }


def test_approval_interrupt_carries_its_approval_id() -> None:
    node = StandardNodeLibrary(dependencies()).create(
        NormalizedNode(
            "approval",
            "interrupt",
            {
                "approval_id": "investigate_outlier",
                "payload": {"candidate": "$.candidate"},
                "result_key": "approval",
            },
        )
    )
    result = run(node, {"candidate": "item-1"})
    assert result == {
        "approval": {
            "decision": {
                "type": "approval_required",
                "approval_id": "investigate_outlier",
                "payload": {"candidate": "item-1"},
            },
        }
    }


def test_unsupported_kind_is_rejected() -> None:
    with pytest.raises(UnsupportedNodeKindError):
        StandardNodeLibrary(dependencies()).create(
            NormalizedNode("domain-node", "application_specific", {})
        )


def test_missing_required_config_is_rejected() -> None:
    with pytest.raises(NodeConfigurationError, match="output_contract"):
        StandardNodeLibrary(dependencies()).create(
            NormalizedNode(
                "model-node",
                "model",
                {
                    "prompt": "prompt",
                    "result_key": "result",
                },
            )
        )
