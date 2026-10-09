package com.asml.analytics.lanadb.mcp.waferkpi;

import java.util.List;
import java.util.Objects;
import java.util.StringJoiner;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;

/** SQL for wafer level KPIs, equivalent to the LanaDB QueryDSL repository plus chuck id. */
record WaferLevelKpiQuery(String sql, MapSqlParameterSource parameters) {

    private static final String SELECT = """
            SELECT les.product_id,
                   les.key_lot_id AS lot_id,
                   les.key_layer_id AS layer_id,
                   wes.wafer_id,
                   wes.chuck_id,
                   lms.id AS measure_process_job_id,
                   les.machine_id AS exposure_equipment_id,
                   lms.machine_id AS measurement_equipment_id,
                   les.lot_start,
                   ROUND(wok.measured_raw_m3s_x, 2)::double precision AS kpi_value1,
                   ROUND(wok.measured_raw_m3s_y, 2)::double precision AS kpi_value2,
                   COALESCE(BOOL_OR(mdp.proxy), false) AS needs_ingestion
            FROM {s}.wafer_metrology_step wms
            JOIN {s}.wafer_kpi_mapping wkm ON wkm.wafer_metrology_step_id = wms.id
            JOIN {s}.wafer_metrology_overlay_kpis wok ON wok.id = wkm.id
            JOIN {s}.wafer_exposure_step wes ON wes.id = wkm.wafer_exposure_step_id
            JOIN {s}.lot_exposure_step les ON les.id = wes.lot_exposure_step_id
            JOIN {s}.lot_metrology_step lms ON lms.id = wms.lot_metrology_step_id
            LEFT JOIN {s}.measure_lot_data_record mldr ON mldr.lot_metrology_step_id = lms.id
            LEFT JOIN {s}.measure_dataset_partition mdp ON mdp.measure_lot_data_record_id = mldr.id
            """;

    private static final String GROUP_ORDER_LIMIT = """

            GROUP BY wms.id, les.product_id, les.key_lot_id, les.key_layer_id, wes.wafer_id, wes.chuck_id,
                     lms.id, les.machine_id, lms.machine_id, les.lot_start,
                     wok.measured_raw_m3s_x, wok.measured_raw_m3s_y
            ORDER BY wms.id ASC
            LIMIT :limit""";

    /** {@code schema} must already be validated as a plain lower-case identifier. */
    static WaferLevelKpiQuery build(String schema, WaferLevelKpiRequest request, int limit) {
        var parameters = new MapSqlParameterSource()
                .addValue("lotExposureStartFrom", request.lotExposureStartFrom())
                .addValue("limit", limit);
        var where = new StringJoiner("\n  AND ", "WHERE ", "");
        if (request.lotExposureStartTo() == null) {
            where.add("les.lot_start >= :lotExposureStartFrom");
        } else {
            parameters.addValue("lotExposureStartTo", request.lotExposureStartTo());
            where.add("les.lot_start BETWEEN :lotExposureStartFrom AND :lotExposureStartTo");
        }
        in(where, parameters, "les.product_id", "productIds", request.productIds());
        in(where, parameters, "les.key_layer_id", "layerIds", request.layerIds());
        in(where, parameters, "les.machine_id", "exposureEquipmentIds", request.exposureEquipmentIds());
        in(where, parameters, "les.key_lot_id", "lotIds", request.lotIds());
        in(where, parameters, "wes.chuck_id", "chuckIds", request.chuckIds());
        where.add("wok.measured_raw_m3s_x IS NOT NULL");
        where.add("wok.measured_raw_m3s_y IS NOT NULL");
        String sql = SELECT.replace("{s}", '"' + schema + '"') + where + GROUP_ORDER_LIMIT;
        return new WaferLevelKpiQuery(sql, parameters);
    }

    private static void in(
            StringJoiner where, MapSqlParameterSource parameters, String column, String name, List<String> values) {
        if (values.isEmpty()) {
            return;
        }
        List<String> nonNull = values.stream().filter(Objects::nonNull).distinct().toList();
        if (nonNull.isEmpty()) {
            where.add(column + " IS NULL");
            return;
        }
        parameters.addValue(name, nonNull);
        String condition = column + " IN (:" + name + ")";
        where.add(values.contains(null) ? "(" + condition + " OR " + column + " IS NULL)" : condition);
    }
}
