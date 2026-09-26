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
