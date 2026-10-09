package com.asml.analytics.lanadb.mcp.waferkpi;

import java.math.BigDecimal;
import java.time.OffsetDateTime;

/** One wafer measurement; KPI values are raw M3S X/Y rounded to two decimals. */
public record WaferLevelKpi(
        String productId,
        String lotId,
        String layerId,
        String waferId,
        String chuckId,
        BigDecimal measureProcessJobId,
        String exposureEquipmentId,
        String measurementEquipmentId,
        OffsetDateTime lotStart,
        double kpiValue1,
        double kpiValue2,
        boolean needsIngestion) {
}
