"""Create LangGraph resume commands without leaking LangGraph into API models."""
from __future__ import annotations
from typing import Any, Mapping


def create_resume_command(*, approved: bool, selected_outlier_id: str | None, comment: str | None, values: Mapping[str, Any]) -> Any:
    payload = {
        "approved": approved,
        "selected_outlier_id": selected_outlier_id,
        "comment": comment,
        "values": dict(values),
    }
    try:
        from langgraph.types import Command
        return Command(resume=payload)
    except ImportError:
        return {"resume": payload}
