"""Registry of standard node factories available to graph compilation."""
from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from .approval import create_approval_node
from .model import create_structured_model_node
from .state import create_assign_node, create_copy_node, create_status_node
from .tool import create_tool_node
from .validation import create_contract_validation_node
from .errors import StandardNodeConfigurationError

@dataclass(frozen=True)
class StandardNodeFactory:
    node_type: str
    create: Callable[..., Any]

class StandardNodeLibrary:
    def __init__(self) -> None:
        self._factories = {
            item.node_type: item
            for item in (
                StandardNodeFactory("model", create_structured_model_node),
                StandardNodeFactory("tool", create_tool_node),
                StandardNodeFactory("approval", create_approval_node),
                StandardNodeFactory("validate", create_contract_validation_node),
                StandardNodeFactory("assign", create_assign_node),
                StandardNodeFactory("copy", create_copy_node),
                StandardNodeFactory("status", create_status_node),
            )
        }
    def require(self, node_type: str) -> StandardNodeFactory:
        try: return self._factories[node_type]
        except KeyError as exc: raise StandardNodeConfigurationError(f"Unknown standard node type: {node_type!r}") from exc
    def list_types(self) -> tuple[str, ...]: return tuple(sorted(self._factories))
