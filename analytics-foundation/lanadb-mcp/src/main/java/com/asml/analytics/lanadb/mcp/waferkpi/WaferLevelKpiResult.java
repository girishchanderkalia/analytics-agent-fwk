package com.asml.analytics.lanadb.mcp.waferkpi;

import java.util.List;

/** {@code truncated} is set when more rows matched than the configured maximum. */
public record WaferLevelKpiResult(List<WaferLevelKpi> rows, int rowCount, boolean truncated) {
}
