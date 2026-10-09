package com.asml.analytics.lanadb.mcp.waferkpi;

import com.asml.analytics.lanadb.mcp.config.LanadbProperties;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class WaferLevelKpiRepository {

    private static final Logger LOGGER = LoggerFactory.getLogger(WaferLevelKpiRepository.class);

    private final NamedParameterJdbcTemplate jdbc;
    private final LanadbProperties properties;

    public WaferLevelKpiRepository(NamedParameterJdbcTemplate jdbc, LanadbProperties properties) {
        this.jdbc = jdbc;
        this.properties = properties;
    }

    public WaferLevelKpiResult getWaferLevelKpis(WaferLevelKpiRequest request) {
        LOGGER.info("Executing query for wafer level kpi with constraints: {}", request);
        int maxRows = properties.maxRows();
        // One extra row detects truncation without a separate COUNT query.
        var query = WaferLevelKpiQuery.build(properties.schema(), request, maxRows + 1);
        LOGGER.debug("Wafer level kpi SQL: {}", query.sql());
        List<WaferLevelKpi> rows = jdbc.query(query.sql(), query.parameters(), WaferLevelKpiRepository::map);
        boolean truncated = rows.size() > maxRows;
        List<WaferLevelKpi> returned = truncated ? List.copyOf(rows.subList(0, maxRows)) : rows;
        return new WaferLevelKpiResult(returned, returned.size(), truncated);
    }

    private static WaferLevelKpi map(ResultSet row, int rowNumber) throws SQLException {
        return new WaferLevelKpi(
                row.getString("product_id"),
                row.getString("lot_id"),
                row.getString("layer_id"),
                row.getString("wafer_id"),
                row.getString("chuck_id"),
                row.getBigDecimal("measure_process_job_id"),
                row.getString("exposure_equipment_id"),
                row.getString("measurement_equipment_id"),
                row.getObject("lot_start", OffsetDateTime.class),
                row.getDouble("kpi_value1"),
                row.getDouble("kpi_value2"),
                row.getBoolean("needs_ingestion"));
    }
}
