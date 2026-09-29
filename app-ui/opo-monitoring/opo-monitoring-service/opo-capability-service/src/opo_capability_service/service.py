from __future__ import annotations
from calendar import monthrange
from collections.abc import Mapping
from datetime import date, timedelta
import re
from typing import Any
from opo_deterministic_logic import analyse_series, classify_wafer_spatial_pattern, detect_outliers, normalize_wafer_rows
from .errors import CapabilityInputError, UnknownCapabilityError
from .models import AnalyseTrendsRequest, ClassifySpatialPatternRequest, NormalizeWaferEvidenceRequest

class OpoCapabilityService:
    def invoke(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        try:
            if name == "normalize_trend_window":
                filters = dict(arguments["filters"])
                question = str(arguments.get("question") or "")
                explicit_year = re.search(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+\s+\d{4})\b", question)
                if question and not explicit_year:
                    matching_months = {
                        month for scope in arguments.get("available_scopes", [])
                        if scope.get("product") in filters.get("product_ids", [])
                        and scope.get("layer") in filters.get("layer_ids", [])
                        and scope.get("scanner") in filters.get("exposure_equipment_ids", [])
                        for month in scope.get("months", [])
                    }
                    if matching_months and filters.get("start_date"):
                        parsed_start = date.fromisoformat(filters["start_date"])
                        possible_starts = []
                        for year in sorted({int(month[:4]) for month in matching_months}):
                            try:
                                candidate = parsed_start.replace(year=year)
                            except ValueError:
                                continue
                            next_month = candidate.month % 12 + 1
                            next_year = candidate.year + (candidate.month == 12)
                            next_start = date(next_year, next_month, min(candidate.day, monthrange(next_year, next_month)[1]))
                            if any(candidate.isoformat()[:7] <= month <= (next_start - timedelta(days=1)).isoformat()[:7] for month in matching_months):
                                possible_starts.append(candidate)
                        if possible_starts:
                            filters["start_date"] = max(possible_starts).isoformat()
                    if not matching_months or not filters.get("start_date") or not possible_starts:
                        filters["start_date"] = None
                        filters["end_date"] = None
                        return {"trend_filters": filters}
                start = date.fromisoformat(filters["start_date"])
                next_month = start.month % 12 + 1
                next_year = start.year + (start.month == 12)
                next_start = date(next_year, next_month, min(start.day, monthrange(next_year, next_month)[1]))
                filters["end_date"] = (next_start - timedelta(days=1)).isoformat()
                filters["lookback_days"] = None
                return {"trend_filters": filters}
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
