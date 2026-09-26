"""Standard structured-model node."""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any, Callable
from .common import public_state, require_mapping, require_name
from .errors import StandardNodeExecutionError


def create_structured_model_node(
    *,
    dependencies: Any,
    prompt_id: str,
    contract_id: str,
    output_field: str,
    input_builder: Callable[[Mapping[str, Any]], str] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    prompt_name = require_name(prompt_id, "prompt_id")
    contract_name = require_name(contract_id, "contract_id")
    target = require_name(output_field, "output_field")

    def node(state: dict[str, Any]) -> dict[str, Any]:
        snapshot = public_state(state)
        prompt_provider = dependencies.prompt_provider
        contract_provider = dependencies.contract_provider
        model_provider = dependencies.model_provider
        try:
            prompt = prompt_provider.get_prompt(prompt_name)
            contract = contract_provider.get_contract(contract_name)
            input_text = input_builder(snapshot) if input_builder else str(snapshot.get("question", ""))
            result = model_provider.invoke_structured(
                system_prompt=prompt,
                input_text=input_text,
                output_contract=contract,
            )
        except Exception as exc:
            raise StandardNodeExecutionError(
                f"Structured model node failed for prompt {prompt_name!r}"
            ) from exc
        if hasattr(result, "model_dump"):
            result = result.model_dump(mode="python")
        return {target: dict(require_mapping(result, "structured model result"))}
    return node
