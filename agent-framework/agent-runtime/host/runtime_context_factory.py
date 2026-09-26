"""Create per-agent execution contexts from fixed framework components."""
from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from bootstrap.capability_dispatcher_adapter import CapabilityRegistryProtocol, create_capability_dispatcher
from bootstrap.contract_provider import ContractProviderCache
from bootstrap.model_gateway_adapter import PlatformModelGateway, create_model_gateway
from bootstrap.operation_registry_bootstrap import OperationHandler, create_operation_registry, validate_workflow_operations
from execution.execution_context import ExecutionContext

class RuntimeContextFactoryError(RuntimeError):
    """Raised when an execution context cannot be created."""

@dataclass(frozen=True)
class ExecutionSecurityContext:
    """Authorization context applied to workflow capability calls."""
    permissions: frozenset[str] = field(default_factory=frozenset)
    approved_capabilities: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        object.__setattr__(self, "permissions", frozenset(self.permissions))
        object.__setattr__(self, "approved_capabilities", frozenset(self.approved_capabilities))

class RuntimeContextFactory:
    """Create isolated execution contexts for resolved agent bundles."""
    def __init__(
        self,
        capability_registry: CapabilityRegistryProtocol,
        operations: Mapping[str, OperationHandler],
        security_context: ExecutionSecurityContext | None = None,
        model_gateway: PlatformModelGateway | None = None,
        contract_provider_cache: ContractProviderCache | None = None,
    ) -> None:
        if not isinstance(operations, Mapping):
            raise RuntimeContextFactoryError("operations must be a mapping")
        self.operations = dict(operations)
        self.security_context = security_context or ExecutionSecurityContext()
        self.model_gateway = model_gateway or create_model_gateway()
        self.capability_dispatcher = create_capability_dispatcher(capability_registry)
        self.operation_registry = create_operation_registry(self.operations)
        self.contract_provider_cache = contract_provider_cache or ContractProviderCache()

    def create(self, bundle: Any) -> ExecutionContext:
        if bundle is None:
            raise RuntimeContextFactoryError("bundle must not be None")
        validate_workflow_operations(bundle, self.operations)
        contract_provider = self.contract_provider_cache.get_or_create(bundle)
        return ExecutionContext(
            model_gateway=self.model_gateway,
            capability_dispatcher=self.capability_dispatcher,
            operation_registry=self.operation_registry,
            contract_provider=contract_provider,
            permissions=self.security_context.permissions,
            approved_capabilities=self.security_context.approved_capabilities,
        )

    def create_context(self, bundle: Any) -> ExecutionContext:
        return self.create(bundle)

    def invalidate_contracts(self, agent_id: str | None = None, version: str | None = None) -> None:
        self.contract_provider_cache.invalidate(agent_id=agent_id, version=version)
