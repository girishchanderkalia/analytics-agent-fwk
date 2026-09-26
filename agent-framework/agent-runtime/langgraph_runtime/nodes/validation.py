"""Standard contract-validation node."""
from __future__ import annotations
from typing import Any, Callable
from .common import public_state, read_path, require_name
from .errors import StandardNodeExecutionError


def create_contract_validation_node(
    *,
    dependencies: Any,
    source_path: str,
    contract_id: str,
    output_field: str | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    source = require_name(source_path, "source_path")
    contract_name = require_name(contract_id, "contract_id")
    target = require_name(output_field, "output_field") if output_field is not None else source.split(".")[-1]

    def node(state: dict[str, Any]) -> dict[str, Any]:
        snapshot = public_state(state)
        value = read_path(snapshot, source)
        try:
            contract = dependencies.contract_provider.get_contract(contract_name)
            if hasattr(contract, "model_validate"):
                validated = contract.model_validate(value)
                value = validated.model_dump(mode="python")
            elif callable(contract):
                value = contract(value)
            else:
                raise TypeError("Contract must expose model_validate or be callable")
        except Exception as exc:
            raise StandardNodeExecutionError(
                f"Contract validation failed for {contract_name!r}"
            ) from exc
        return {target: value}
    return node
