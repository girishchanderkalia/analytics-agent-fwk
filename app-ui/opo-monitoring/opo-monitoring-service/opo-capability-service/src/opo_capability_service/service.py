from __future__ import annotations
from calendar import monthrange
from collections.abc import Callable, Mapping
from datetime import date, timedelta
import re
from typing import Any
from opo_deterministic_logic import analyse_series, classify_wafer_spatial_pattern, compare_tdbb_budgets, detect_outliers, normalize_wafer_rows, suggest_change_date
from .errors import CapabilityInputError, UnknownCapabilityError
from .models import AnalyseTrendsRequest, ClassifySpatialPatternRequest, CompareTdbbBudgetsRequest, NormalizeWaferEvidenceRequest, SuggestChangeDateRequest

EXPLICIT_YEAR = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+,?\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})\b")

def _with_year(value: date, year: int) -> date:
    return value.replace(year=year, day=min(value.day, monthrange(year, value.month)[1]))

class OpoCapabilityService:
    def __init__(self, today: Callable[[], date] = date.today) -> None:
        self.today = today

    def invoke(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        try:
            if name == "normalize_trend_window":
                filters = dict(arguments["filters"])
                if not filters.get("start_date"):
                    filters["end_date"] = None
                    return {"trend_filters": filters}
                start = date.fromisoformat(filters["start_date"])
                question = str(arguments.get("question") or "")
                if question and not EXPLICIT_YEAR.search(question):
                    # A date without a year means the most recent occurrence up to today.
                    today = self.today()
                    start = _with_year(start, today.year)
                    if start > today:
                        start = _with_year(start, today.year - 1)
                next_month = start.month % 12 + 1
                next_year = start.year + (start.month == 12)
                next_start = date(next_year, next_month, min(start.day, monthrange(next_year, next_month)[1]))
                filters["start_date"] = start.isoformat()
                filters["end_date"] = (next_start - timedelta(days=1)).isoformat()
                filters["lookback_days"] = None
                return {"trend_filters": filters}
            if name == "resolve_change_date":
                scope = dict(arguments.get("scope") or {})
                start = date.fromisoformat(arguments["start_date"])
                end = date.fromisoformat(arguments["end_date"])
                if not scope.get("change_date"):
                    return {"comparison_scope": {**scope, "change_date": None}}
                change = date.fromisoformat(str(scope["change_date"])[:10])
                if not EXPLICIT_YEAR.search(str(arguments.get("question") or "")):
                    # A day without a year means that day inside the analysed window.
                    change = next((c for c in (_with_year(change, y) for y in sorted({start.year, end.year})) if start < c <= end), change)
                if not start < change <= end:
                    scope["interpretation"] = (
                        f"{scope.get('interpretation', '')} The change date {change.isoformat()} is outside the "
                        f"analysed window after {start.isoformat()} up to {end.isoformat()}."
                    ).strip()
                    return {"comparison_scope": {**scope, "change_date": None}}
                return {"comparison_scope": {**scope, "change_date": change.isoformat()}}
            if name == "suggest_change_date":
                request = SuggestChangeDateRequest.model_validate(arguments)
                return suggest_change_date(request.series, request.end_date)
            if name == "compare_tdbb_budgets":
                request = CompareTdbbBudgetsRequest.model_validate(arguments)
                return compare_tdbb_budgets(request.periods)
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
