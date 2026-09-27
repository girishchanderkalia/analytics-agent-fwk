"""Generic declarative agent-package definitions and normalization."""

from .markdown_translator import translate_bundle, translate_markdown_agent
from .normalization_errors import DefinitionNormalizationError
from .normalized_models import (
    NormalizedAgentDefinition,
    NormalizedEdge,
    NormalizedGraph,
    NormalizedNode,
    NormalizedPrompt,
    NormalizedState,
)

__all__ = [
    "DefinitionNormalizationError",
    "NormalizedAgentDefinition",
    "NormalizedEdge",
    "NormalizedGraph",
    "NormalizedNode",
    "NormalizedPrompt",
    "NormalizedState",
    "translate_bundle",
    "translate_markdown_agent",
]
