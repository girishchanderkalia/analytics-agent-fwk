from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ToolDefinition:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]

TOOLS = (
    ToolDefinition(
        "normalize_trend_window", "Normalize OPO trend window",
        "Resolve a missing year to the current year and set the inclusive end date one calendar month after the start date.",
        {"type":"object","properties":{"filters":{"type":"object"},"question":{"type":"string"}},"required":["filters"],"additionalProperties":False},
    ),
    ToolDefinition(
        "resolve_change_date", "Resolve OPO change date",
        "Resolve a change date without a year into the analysed window and reject dates outside it.",
        {"type":"object","properties":{"scope":{"type":["object","null"]},"question":{"type":"string"},"start_date":{"type":"string"},"end_date":{"type":"string"}},"required":["scope","start_date","end_date"],"additionalProperties":False},
    ),
    ToolDefinition(
        "suggest_change_date", "Suggest OPO change date",
        "Suggest the day the overlay X/Y KPIs stepped, with a prefilled analyst question.",
        {"type":"object","properties":{"series":{"type":"array","items":{"type":"object"}},"end_date":{"type":["string","null"]}},"required":["series"],"additionalProperties":False},
    ),
    ToolDefinition(
        "compare_tdbb_budgets", "Compare TDBB budgets",
        "Compare TDBB budgets after a change date against before it and name the largest increase.",
        {"type":"object","properties":{"periods":{"type":"array","items":{"type":"object"}}},"required":["periods"],"additionalProperties":False},
    ),
    ToolDefinition(
        "analyze_trends", "Analyze OPO trends",
        "Apply application-owned threshold and outlier rules to retrieved trend series.",
        {"type":"object","properties":{"series":{"type":"array","items":{"type":"object"}},"mode":{"type":"string","enum":["baseline","absolute"]},"limit_value":{"type":["number","null"]},"direction":{"type":"string","enum":["above","below"]},"baseline_deviation_pct":{"type":"number","minimum":0},"limit_unit":{"type":"string","enum":["percent","absolute"]}},"required":["series"],"additionalProperties":False},
    ),
    ToolDefinition(
        "normalize_wafer_evidence", "Normalize wafer evidence",
        "Normalize retrieved wafer rows and identify anomalous wafers.",
        {"type":"object","properties":{"rows":{"type":"array","items":{"type":"object"}},"filters":{"type":"object"},"anomaly_threshold_um":{"type":"number","minimum":0}},"required":["rows"],"additionalProperties":False},
    ),
    ToolDefinition(
        "classify_spatial_pattern", "Classify spatial pattern",
        "Classify anomalous wafer points by radial position.",
        {"type":"object","properties":{"rows":{"type":"array","items":{"type":"object"}},"anomalous_wafer_ids":{"type":"array","items":{"type":"string"}}},"required":["rows","anomalous_wafer_ids"],"additionalProperties":False},
    ),
)
TOOL_BY_NAME = {tool.name: tool for tool in TOOLS}
