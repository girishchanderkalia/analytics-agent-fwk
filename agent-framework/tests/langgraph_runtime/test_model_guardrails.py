from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent-framework" / "agent-runtime"))

from definitions import NormalizedNode
from definitions.normalization_errors import DefinitionNormalizationError
from definitions.markdown_translator import _guardrails
from execution.output_rules import check_output
from langgraph_runtime.standard_nodes import NodeExecutionError, StandardNodeDependencies, StandardNodeLibrary
from mcp_tools import McpToolRegistry

STATE = {
    "window": {"start": "2026-08-17", "end": "2026-09-16"},
    "question": "I observe a jump from 1 Sep to 16 Sep in GW021",
    "evidence": {"before": 0.742, "after": 1.542, "pct": 107.8, "lots": 30},
}


def test_date_rules() -> None:
    rules = [
        {"field": "change_date", "rule": "iso_date"},
        {"field": "change_date", "rule": "date_between", "after": "$.window.start", "until": "$.window.end"},
        {"field": "change_date", "rule": "mentioned_in", "source": "$.question"},
    ]
    assert check_output({"change_date": "2026-09-01"}, rules, STATE) == []
    violations = check_output({"change_date": "2026-09-20"}, rules, STATE)
    assert violations == [
        "change_date: 2026-09-20 must be on or before 2026-09-16",
        "change_date: 2026-09-20 not mentioned in the source",
    ]


def test_required_one_of_and_mentions_on_lists() -> None:
    rules = [
        {"field": "scanners", "rule": "required"},
        {"field": "scanners", "rule": "mentioned_in", "source": "$.question"},
        {"field": "level", "rule": "one_of", "values": ["low", "high"]},
    ]
    assert check_output({"scanners": ["GW021"], "level": "low"}, rules, STATE) == []
    assert check_output({"scanners": ["GW099"], "level": "odd"}, rules, STATE) == [
        "scanners: GW099 not mentioned in the source",
        "level: odd not one of the allowed values",
    ]
    assert check_output({"scanners": [], "level": "low"}, rules, STATE) == ["scanners: is required"]


def test_numbers_phrases_and_length_on_text() -> None:
    rules = [
        {"field": "message", "rule": "numbers_from", "source": "$.evidence", "tolerance": 0.01},
        {"field": "message", "rule": "forbidden_phrases", "values": ["root cause", "due to"]},
        {"field": "message", "rule": "max_length", "max": 80},
    ]
    assert check_output({"message": "NCE rose 0.742 -> 1.54 nm (+107.8%) over 30 lots"}, rules, STATE) == []
    violations = check_output({"message": "NCE rose to 1.9 nm due to the reticle"}, rules, STATE)
    assert violations == ["message: numbers 1.9 are not in the source", "message: contains forbidden phrases ['due to']"]


def test_formula_checks_each_list_item_against_its_siblings() -> None:
    rules = [{"field": "rows[].delta", "rule": "formula", "equals": "after - before", "tolerance": 0.001}]
    output = {"rows": [{"before": 1.0, "after": 1.5, "delta": 0.5}, {"before": 1.0, "after": 1.5, "delta": 0.7}, {"before": None, "after": 1.5, "delta": None}]}
    assert check_output(output, rules, {}) == ["rows[1].delta: 0.7 should equal after - before = 0.5"]


def test_output_references_resolve_against_the_model_output() -> None:
    rules = [{"field": "change_date", "rule": "mentioned_in", "source": "${output.question}"}]
    assert check_output({"change_date": "2026-09-01", "question": "jump from 1 Sep 2026"}, rules, {}) == []


def test_unsupported_rule_and_missing_parameters_are_rejected_at_translation() -> None:
    with pytest.raises(DefinitionNormalizationError, match="unsupported rule"):
        _guardrails({"report_to": "report", "rules": [{"field": "x", "rule": "sentiment"}]}, "n")
    with pytest.raises(DefinitionNormalizationError, match="requires source"):
        _guardrails({"report_to": "report", "rules": [{"field": "x", "rule": "mentioned_in"}]}, "n")
    with pytest.raises(DefinitionNormalizationError, match="warn or stop"):
        _guardrails({"report_to": "report", "on_failure": "ignore", "rules": [{"field": "x", "rule": "required"}]}, "n")


class Prompts:
    def render(self, prompt_id, state):
        return prompt_id


class Contracts:
    def get_contract(self, name):
        return name


class ScriptedModel:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []

    async def invoke_structured(self, **kwargs):
        self.requests.append(kwargs)
        return self.answers.pop(0)


def guarded_node(model, on_failure="warn", retries=1):
    deps = StandardNodeDependencies(model_provider=model, prompt_provider=Prompts(), contract_provider=Contracts(), tool_registry=McpToolRegistry(), tool_invoker=None)
    config = {
        "prompt": "p",
        "output_contract": "C",
        "result_key": "scope",
        "inputs": ["question"],
        "guardrails": _guardrails({
            "report_to": "guardrail_report",
            "retries": retries,
            "on_failure": on_failure,
            "rules": [{"field": "change_date", "rule": "date_between", "after": "${state.window.start}", "until": "${state.window.end}"}],
        }, "interpret"),
    }
    return StandardNodeLibrary(deps).create(NormalizedNode("interpret", "model", config))


def test_violation_is_corrected_on_retry_with_the_violations_as_feedback() -> None:
    model = ScriptedModel({"change_date": "2025-09-01"}, {"change_date": "2026-09-01"})
    result = asyncio.run(guarded_node(model)(STATE))
    assert result["scope"] == {"change_date": "2026-09-01"}
    assert result["guardrail_report"]["interpret"]["status"] == "corrected"
    assert "must be after 2026-08-17" in model.requests[1]["input_text"]


def test_persistent_violation_warns_and_keeps_the_last_answer() -> None:
    model = ScriptedModel({"change_date": "2025-09-01"}, {"change_date": "2025-09-02"})
    result = asyncio.run(guarded_node(model)({**STATE, "guardrail_report": {"earlier": {"status": "passed"}}}))
    report = result["guardrail_report"]
    assert result["scope"]["change_date"] == "2025-09-02"
    assert report["interpret"]["status"] == "failed" and report["interpret"]["attempts"] == 2
    assert report["earlier"] == {"status": "passed"}


def test_persistent_violation_stops_when_declared() -> None:
    model = ScriptedModel({"change_date": "2025-09-01"}, {"change_date": "2025-09-02"})
    with pytest.raises(NodeExecutionError, match="violates its guardrails"):
        asyncio.run(guarded_node(model, on_failure="stop")(STATE))


def test_passing_output_is_reported_without_retry() -> None:
    model = ScriptedModel({"change_date": "2026-09-01"})
    result = asyncio.run(guarded_node(model)(STATE))
    assert result["guardrail_report"]["interpret"] == {"status": "passed", "attempts": 1, "violations": [], "corrected": []}
    assert len(model.requests) == 1
