from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .evidence import build_evidence


def shape_response(
    result: Mapping[str, Any],
    thread_id: str,
) -> dict[str, Any]:
    """Shape runtime output into the legacy OPO `/chat` and `/resume` contract."""
    normalized_thread_id = _thread_id(thread_id)
    evidence = build_evidence(result)
    interrupt = _first_interrupt(result)
    if interrupt is not None:
        return {
            "thread_id": normalized_thread_id,
            "status": "awaiting_human",
            "request": interrupt,
            "evidence": evidence,
        }
    cancelled_at = result.get("cancelled_at")
    if cancelled_at:
        return {
            "thread_id": normalized_thread_id,
            "status": "cancelled",
            "cancelled_at": cancelled_at,
            "evidence": evidence,
        }
    if not result.get("outliers"):
        return {
            "thread_id": normalized_thread_id,
            "status": "no_outliers",
            "evidence": evidence,
        }
    return {
        "thread_id": normalized_thread_id,
        "status": "complete",
        "findings": result.get("findings"),
        "evidence": evidence,
    }


def shape_thread_state(
    *,
    thread_id: str,
    values: Mapping[str, Any],
    pending_interrupts: Sequence[Any] = (),
) -> dict[str, Any]:
    """Shape a persisted runtime snapshot into the legacy `/threads/{id}` contract."""
    pending = tuple(pending_interrupts)
    return {
        "thread_id": _thread_id(thread_id),
        "status": "awaiting_human" if pending else "idle",
        "request": _interrupt_value(pending[0]) if pending else None,
        "values": dict(values),
    }


def _first_interrupt(result: Mapping[str, Any]) -> Any | None:
    values = result.get("__interrupt__")
    if not values:
        values = result.get("interrupts")
    if not values:
        interrupt = result.get("interrupt")
        if interrupt:
            return _interrupt_value(interrupt)
        return None
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes, bytearray)):
        return _interrupt_value(values[0]) if values else None
    return _interrupt_value(values)


def _interrupt_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return value.get("value", value)
    return getattr(value, "value", value)


def _thread_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("thread_id must be a non-empty string")
    return value.strip()
