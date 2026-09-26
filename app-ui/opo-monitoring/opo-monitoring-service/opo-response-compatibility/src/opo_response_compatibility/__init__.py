"""Legacy OPO API response compatibility."""

from .evidence import EVIDENCE_FIELDS, build_evidence
from .shaper import shape_response, shape_thread_state

__all__ = [
    "EVIDENCE_FIELDS",
    "build_evidence",
    "shape_response",
    "shape_thread_state",
]
