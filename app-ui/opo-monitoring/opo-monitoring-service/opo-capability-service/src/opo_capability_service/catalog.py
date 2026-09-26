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
