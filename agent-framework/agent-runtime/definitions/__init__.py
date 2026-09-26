"""Generic declarative agent-package definitions and normalization."""

from .errors import AgentPackageError, AgentPackageManifestError
from .normalization_errors import DefinitionNormalizationError
from .normalized_models import (
    NormalizedAgentDefinition,
    NormalizedEdge,
    NormalizedGraph,
    NormalizedNode,
    NormalizedPrompt,
    NormalizedState,
)
from .normalizer import normalize_agent_package, normalize_loaded_package
from .package_models import AgentPackageManifest, AgentPackageSources
from .source_loader import LoadedAgentPackage, load_agent_package

__all__ = [
    "AgentPackageError",
    "AgentPackageManifest",
    "AgentPackageManifestError",
    "AgentPackageSources",
    "DefinitionNormalizationError",
    "LoadedAgentPackage",
    "NormalizedAgentDefinition",
    "NormalizedEdge",
    "NormalizedGraph",
    "NormalizedNode",
    "NormalizedPrompt",
    "NormalizedState",
    "load_agent_package",
    "normalize_agent_package",
    "normalize_loaded_package",
]
