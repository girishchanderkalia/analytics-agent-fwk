"""Convert Runtime Service responses to API response models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from .models import RuntimeResponseModel


def plain_value(value: Any) -> Any:
    """Convert enums, dataclasses, and mappings to JSON-compatible values."""

    if isinstance(value, Enum):
        return value.value

    if is_dataclass(value):
        return {
            key: plain_value(item)
            for key, item in asdict(value).items()
        }

    if isinstance(value, Mapping):
        return {
            str(key): plain_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [plain_value(item) for item in value]

    if isinstance(value, tuple):
        return [plain_value(item) for item in value]

    return value


def runtime_response(response: Any) -> RuntimeResponseModel:
    """Create the stable HTTP representation of a RuntimeResponse."""

    return RuntimeResponseModel(
        conversation_id=response.conversation_id,
        agent_id=response.agent_id,
        status=str(plain_value(response.status)),
        version=response.version,
        result=plain_value(response.result),
        approval_request=plain_value(response.approval_request),
    )
