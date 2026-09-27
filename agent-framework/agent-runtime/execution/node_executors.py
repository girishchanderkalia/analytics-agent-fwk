"""Node executors used by the declarative workflow engine."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .execution_context import ExecutionContext
from .execution_models import (
    ApprovalRequest,
    NodeExecutionError,
    NodeExecutionResult,
    NodeType,
)


class NodeExecutor:
    """Execute supported declarative workflow nodes."""

    def execute(
        self,
        *,
        node: Mapping[str, Any],
        state: Mapping[str, Any],
        agent_metadata: Mapping[str, Any],
        knowledge_markdown: str,
        context: ExecutionContext,
    ) -> NodeExecutionResult:
        """Execute one workflow node."""

        node_type = node.get("type")

        try:
            parsed_type = NodeType(node_type)

        except (TypeError, ValueError) as exc:
            raise NodeExecutionError(
                f"Unsupported node type {node_type!r}"
            ) from exc

        if parsed_type is NodeType.MODEL:
            return self._execute_model(
                node=node,
                state=state,
                agent_metadata=agent_metadata,
                knowledge_markdown=knowledge_markdown,
                context=context,
            )

        if parsed_type is NodeType.CAPABILITY:
            return self._execute_capability(
                node=node,
                state=state,
                context=context,
            )

        if parsed_type in {
            NodeType.OPERATION,
            NodeType.DETERMINISTIC,
        }:
            return self._execute_operation(
                node=node,
                state=state,
                context=context,
            )

        if parsed_type is NodeType.APPROVAL:
            return self._execute_approval(
                node=node,
                state=state,
            )

        raise NodeExecutionError(
            f"Node type {node_type!r} has no executor"
        )

    @staticmethod
    def _execute_model(
        *,
        node: Mapping[str, Any],
        state: Mapping[str, Any],
        agent_metadata: Mapping[str, Any],
        knowledge_markdown: str,
        context: ExecutionContext,
    ) -> NodeExecutionResult:
        """Execute one structured model node."""

        node_id = _required_string(
            node,
            "id",
        )

        prompt_name = _required_string(
            node,
            "prompt",
        )

        contract_name = (
            node.get("output_contract")
            or node.get("output")
        )

        if (
            not isinstance(contract_name, str)
            or not contract_name.strip()
        ):
            raise NodeExecutionError(
                f"Model node {node_id!r} must declare "
                "'output_contract' or 'output'"
            )

        contract_name = contract_name.strip()

        output_field = node.get("output_to")

        if output_field is None:
            output_field = _default_output_field(
                contract_name
            )

        if (
            not isinstance(output_field, str)
            or not output_field.strip()
        ):
            raise NodeExecutionError(
                f"Model node {node_id!r} must declare "
                "'output_to', or use a recognized contract"
            )

        output_field = output_field.strip()

        prompts = agent_metadata.get(
            "prompts",
            {},
        )

        if not isinstance(prompts, Mapping):
            raise NodeExecutionError(
                "Agent prompts must be a mapping"
            )

        prompt = prompts.get(prompt_name)

        if (
            not isinstance(prompt, str)
            or not prompt.strip()
        ):
            raise NodeExecutionError(
                f"Model node {node_id!r} references "
                f"unknown prompt {prompt_name!r}"
            )

        output_contract = (
            context.contract_provider.get_contract(
                contract_name
            )
        )

        system_prompt = (
            f"{prompt.strip()}\n\n"
            "Application knowledge:\n"
            f"{knowledge_markdown.strip()}"
        )

        result = context.model_gateway.invoke_structured(
            system_prompt=system_prompt,
            input_text=_build_model_input(state, node.get("inputs")),
            output_contract=output_contract,
        )

        if not isinstance(result, Mapping):
            raise NodeExecutionError(
                f"Model node {node_id!r} returned "
                f"{type(result).__name__}; "
                "expected a mapping"
            )

        return NodeExecutionResult(
            state_update={
                output_field: dict(result),
            }
        )

    @staticmethod
    def _execute_capability(
        *,
        node: Mapping[str, Any],
        state: Mapping[str, Any],
        context: ExecutionContext,
    ) -> NodeExecutionResult:
        """Execute one governed capability node."""

        node_id = _required_string(
            node,
            "id",
        )

        capability_id = _required_string(
            node,
            "capability",
        )

        result = context.capability_dispatcher.invoke(
            capability_id=capability_id,
            state=state,
            permissions=context.permissions,
            approved_capabilities=(
                context.approved_capabilities
            ),
        )

        if not isinstance(result, Mapping):
            raise NodeExecutionError(
                f"Capability node {node_id!r} returned "
                f"{type(result).__name__}; "
                "expected a mapping"
            )

        return NodeExecutionResult(
            state_update=dict(result)
        )

    @staticmethod
    def _execute_operation(
        *,
        node: Mapping[str, Any],
        state: Mapping[str, Any],
        context: ExecutionContext,
    ) -> NodeExecutionResult:
        """Execute one deterministic operation node."""

        node_id = _required_string(
            node,
            "id",
        )

        operation_name = (
            node.get("implementation")
            or node.get("operation")
        )

        if (
            not isinstance(operation_name, str)
            or not operation_name.strip()
        ):
            raise NodeExecutionError(
                f"Operation node {node_id!r} must "
                "declare 'implementation' or 'operation'"
            )

        result = context.operation_registry.invoke(
            operation_name.strip(),
            state,
        )

        if not isinstance(result, Mapping):
            raise NodeExecutionError(
                f"Operation node {node_id!r} returned "
                f"{type(result).__name__}; "
                "expected a mapping"
            )

        output_field = node.get("output_to")

        if (
            isinstance(output_field, str)
            and output_field
            and output_field not in result
        ):
            return NodeExecutionResult(
                state_update={
                    output_field: deepcopy_value(result),
                }
            )

        return NodeExecutionResult(
            state_update=dict(result)
        )

    @staticmethod
    def _execute_approval(
        *,
        node: Mapping[str, Any],
        state: Mapping[str, Any],
    ) -> NodeExecutionResult:
        """Create an approval interruption."""

        node_id = _required_string(
            node,
            "id",
        )

        approval_id = (
            node.get("approval_id")
            or node.get("approval")
        )

        if (
            not isinstance(approval_id, str)
            or not approval_id.strip()
        ):
            raise NodeExecutionError(
                f"Approval node {node_id!r} must "
                "declare 'approval_id' or 'approval'"
            )

        approval_id = approval_id.strip()

        request_contract = (
            node.get("request_contract")
            or node.get("approval")
        )

        if (
            request_contract is not None
            and not isinstance(request_contract, str)
        ):
            raise NodeExecutionError(
                f"Approval node {node_id!r} has "
                "an invalid request contract"
            )

        outliers = state.get(
            "detected_outliers",
            state.get("outliers", []),
        )

        if not isinstance(outliers, list):
            outliers = []

        payload = {
            "detected_outliers": list(outliers),
            "selected_outlier": state.get(
                "selected_outlier"
            ),
        }

        approval_request = ApprovalRequest(
            approval_id=approval_id,
            node_id=node_id,
            public_type="approval_required",
            request_contract=request_contract,
            payload=payload,
        )

        public_request = {
            "approval_id": approval_id,
            "node_id": node_id,
            "public_type": "approval_required",
            "request_contract": request_contract,
            "payload": payload,
        }

        return NodeExecutionResult(
            state_update={
                "status": "waiting_for_approval",
                "pending_approval": public_request,
                "pending_action": public_request,
            },
            approval_request=approval_request,
        )


def _default_output_field(
    contract_name: str,
) -> str | None:
    """Map known model contracts to state fields."""

    mappings = {
        "TrendFilters": "trend_filters",
        "DetectionScope": "detection_scope",
        "FindingsSummary": "findings",
        "InvestigationApproval": "pending_approval",
    }

    return mappings.get(contract_name)


def _required_string(
    mapping: Mapping[str, Any],
    field_name: str,
) -> str:
    """Read a required non-empty string."""

    value = mapping.get(field_name)

    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise NodeExecutionError(
            f"Required field {field_name!r} must "
            "be a non-empty string"
        )

    return value.strip()


def _build_model_input(
    state: Mapping[str, Any],
    fields: Any = None,
) -> str:
    """Build model input from workflow state.

    A node may declare `inputs` to bound what it sends: evidence collections
    such as wafer rows can be far larger than a model context window.
    """

    question = state.get("question", "")
    messages = state.get("messages", [])

    if isinstance(fields, list) and fields:
        selected = {
            name: state[name]
            for name in fields
            if isinstance(name, str) and name in state
        }
    else:
        selected = dict(state)

    return (
        f"Question:\n{question}\n\n"
        f"Workflow state:\n{selected}\n\n"
        f"Conversation messages:\n{messages}"
    )


def deepcopy_value(
    value: Any,
) -> Any:
    """Copy a value returned by an operation."""

    from copy import deepcopy

    return deepcopy(value)