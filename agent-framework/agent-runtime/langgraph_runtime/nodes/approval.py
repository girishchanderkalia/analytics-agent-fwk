"""Standard human-approval interrupt node."""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any, Callable
from langgraph.types import interrupt
from .common import public_state, read_path, require_mapping, require_name
from .errors import StandardNodeExecutionError


def create_approval_node(
    *,
    approval_id: str,
    payload_mapping: Mapping[str, str],
    decision_field: str = "approved",
    comment_field: str = "approval_comment",
    interrupt_function: Callable[[Any], Any] = interrupt,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    identifier = require_name(approval_id, "approval_id")
    decision = require_name(decision_field, "decision_field")
    comment = require_name(comment_field, "comment_field")
    mapping = {require_name(k, "payload field"): require_name(v, "state path") for k, v in payload_mapping.items()}
    def node(state: dict[str, Any]) -> dict[str, Any]:
        snapshot = public_state(state)
        request = {
            "type": "approval_required",
            "approvalId": identifier,
            "payload": {target: read_path(snapshot, source) for target, source in mapping.items()},
        }
        response = require_mapping(interrupt_function(request), "approval response")
        if "approved" not in response or not isinstance(response["approved"], bool):
            raise StandardNodeExecutionError("Approval response must contain a boolean 'approved'")
        return {
            decision: response["approved"],
            comment: response.get("comment"),
            "pending_approval": None,
        }
    return node
