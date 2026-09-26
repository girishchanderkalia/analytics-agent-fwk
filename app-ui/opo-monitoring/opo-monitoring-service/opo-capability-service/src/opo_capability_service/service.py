from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from opo_deterministic_logic import analyse_series, classify_wafer_spatial_pattern, normalize_wafer_rows
from .errors import CapabilityInputError, UnknownCapabilityError
from .models import AnalyseTrendsRequest, ClassifySpatialPatternRequest, NormalizeWaferEvidenceRequest

class OpoCapabilityService:
    def invoke(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        try:
            if name == "analyze_trends":
                request=AnalyseTrendsRequest.model_validate(arguments)
                analysis=analyse_series(request.series, mode=request.mode, limit_value=request.limit_value, direction=request.direction, baseline_deviation_pct=request.baseline_deviation_pct, limit_unit=request.limit_unit)
                return {"analysis": analysis}
            if name == "normalize_wafer_evidence":
                request=NormalizeWaferEvidenceRequest.model_validate(arguments)
                return normalize_wafer_rows(request.rows, filters=request.filters, anomaly_threshold_um=request.anomaly_threshold_um)
            if name == "classify_spatial_pattern":
                request=ClassifySpatialPatternRequest.model_validate(arguments)
                return classify_wafer_spatial_pattern(request.rows, request.anomalous_wafer_ids)
        except Exception as exc:
            if isinstance(exc, UnknownCapabilityError):
                raise
            raise CapabilityInputError(str(exc)) from exc
        raise UnknownCapabilityError(name)
