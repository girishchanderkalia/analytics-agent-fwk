
###############################################################################
# execution_context.py
###############################################################################

"""Execution dependencies supplied by the Agent Runtime host."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class ModelGateway(Protocol):
    """Interface used by model workflow nodes."""

    def invoke_structured(
        self,
        *,
        system_prompt: str,
        input_text: str,
        output_contract: type[Any],
    ) -> Mapping[str, Any]:
        """Invoke a model and return a structured result."""


@runtime_checkable
class ContractProvider(Protocol):
    """Provides generated Python contracts by logical contract name."""

    def get_contract(
        self,
        contract_name: str,
    ) -> type[Any]:
        """Resolve one generated contract class."""


@runtime_checkable
class CapabilityDispatcher(Protocol):
    """Executes one governed Analytics Foundation capability."""

    def invoke(
        self,
        *,
        capability_id: str,
        state: Mapping[str, Any],
        permissions: frozenset[str],
        approved_capabilities: frozenset[str],
    ) -> Mapping[str, Any]:
        """Invoke a capability and return a state update."""


@runtime_checkable
class OperationInvoker(Protocol):
    """Executes a registered deterministic operation."""

    def invoke(
        self,
        name: str,
        state: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Invoke a deterministic operation."""


@dataclass(frozen=True)
class ExecutionContext:
    """Dependencies and security context for one workflow execution."""

    model_gateway: ModelGateway
    contract_provider: ContractProvider
    capability_dispatcher: CapabilityDispatcher
    operation_registry: OperationInvoker
    permissions: frozenset[str] = frozenset()
    approved_capabilities: frozenset[str] = frozenset()