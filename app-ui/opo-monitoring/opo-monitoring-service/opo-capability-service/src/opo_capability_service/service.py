from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from opo_deterministic_logic import analyse_series, classify_wafer_spatial_pattern, detect_outliers, normalize_wafer_rows
from .errors import CapabilityInputError, UnknownCapabilityError
from .models import AnalyseTrendsRequest, ClassifySpatialPatternRequest, NormalizeWaferEvidenceRequest

class OpoCapabilityService:
    def invoke(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        try:
            if name == "analyze_trends":
                request=AnalyseTrendsRequest.model_validate(arguments)
                # A null value means the caller expressed no preference.
                rules={"mode":request.mode or "baseline","limit_value":request.limit_value,"direction":request.direction or "below","baseline_deviation_pct":3.0 if request.baseline_deviation_pct is None else request.baseline_deviation_pct,"limit_unit":request.limit_unit or "percent"}
                return {"analysis": analyse_series(request.series, **rules), "outliers": detect_outliers(request.series, **rules)}
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
