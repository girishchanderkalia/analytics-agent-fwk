"""Capability registration, mapping, and adaptor components."""

from .analytics_foundation_adaptor import (
    AnalyticsFoundationAdaptor,
    AnalyticsFoundationAdaptorError,
)
from .capability_mapping import (
    CapabilityMappingError,
    map_request,
    map_result,
    map_value,
    resolve_reference,
)
from .capability_models import (
    CapabilityContext,
    CapabilityDefinition,
    CapabilityHandler,
    CapabilityInvocation,
    CapabilityRequest,
    CapabilityResult,
)
from .capability_registry import (
    CapabilityAlreadyRegisteredError,
    CapabilityApprovalError,
    CapabilityExecutionError,
    CapabilityNotFoundError,
    CapabilityPermissionError,
    CapabilityRegistry,
    CapabilityRegistryError,
    InvalidCapabilityError,
)

__all__ = [
    "AnalyticsFoundationAdaptor",
    "AnalyticsFoundationAdaptorError",
    "CapabilityAlreadyRegisteredError",
    "CapabilityApprovalError",
    "CapabilityContext",
    "CapabilityDefinition",
    "CapabilityExecutionError",
    "CapabilityHandler",
    "CapabilityInvocation",
    "CapabilityMappingError",
    "CapabilityNotFoundError",
    "CapabilityPermissionError",
    "CapabilityRegistry",
    "CapabilityRegistryError",
    "CapabilityRequest",
    "CapabilityResult",
    "InvalidCapabilityError",
    "map_request",
    "map_result",
    "map_value",
    "resolve_reference",
]