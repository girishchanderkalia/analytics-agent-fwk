package com.asml.analytics.lanadb.mcp.waferkpi;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.OffsetDateTime;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Test;

class WaferLevelKpiQueryTest {

    private static final OffsetDateTime FROM = OffsetDateTime.parse("2024-09-01T00:00:00Z");
    private static final OffsetDateTime TO = OffsetDateTime.parse("2024-09-17T00:00:00Z");

    private static WaferLevelKpiRequest request(List<String> productIds, List<String> chuckIds) {
        return new WaferLevelKpiRequest(FROM, TO, productIds, List.of(), List.of(), List.of(), chuckIds);
    }

    @Test
    void usesSchemaWindowRequiredKpisGroupingAndLimit() {
        var query = WaferLevelKpiQuery.build("lisa", request(List.of(), List.of()), 11);

        assertThat(query.sql())
                .contains("FROM \"lisa\".wafer_metrology_step wms")
                .contains("LEFT JOIN \"lisa\".measure_dataset_partition mdp")
                .contains("les.lot_start BETWEEN :lotExposureStartFrom AND :lotExposureStartTo")
                .contains("wok.measured_raw_m3s_x IS NOT NULL")
                .contains("wok.measured_raw_m3s_y IS NOT NULL")
                .contains("COALESCE(BOOL_OR(mdp.proxy), false) AS needs_ingestion")
                .contains("ORDER BY wms.id ASC")
                .doesNotContain(" IN (");
        assertThat(query.parameters().getValue("lotExposureStartFrom")).isEqualTo(FROM);
        assertThat(query.parameters().getValue("lotExposureStartTo")).isEqualTo(TO);
        assertThat(query.parameters().getValue("limit")).isEqualTo(11);
    }

    @Test
    void openEndedWindowHasOnlyLowerBound() {
        var request = new WaferLevelKpiRequest(FROM, null, List.of(), List.of(), List.of(), List.of(), List.of());

        var query = WaferLevelKpiQuery.build("lisa", request, 10);

        assertThat(query.sql()).contains("les.lot_start >= :lotExposureStartFrom").doesNotContain("BETWEEN");
        assertThat(query.parameters().hasValue("lotExposureStartTo")).isFalse();
    }

    @Test
    void bindsNonNullIdsAsInConstraint() {
        var query = WaferLevelKpiQuery.build("lisa", request(List.of("AAA2", "AAA2", "BBB1"), List.of("Chuck1")), 10);

        assertThat(query.sql())
                .contains("les.product_id IN (:productIds)")
                .contains("wes.chuck_id IN (:chuckIds)")
                .doesNotContain("les.product_id IS NULL");
        assertThat(query.parameters().getValue("productIds")).isEqualTo(List.of("AAA2", "BBB1"));
        assertThat(query.parameters().getValue("chuckIds")).isEqualTo(List.of("Chuck1"));
    }

    @Test
    void onlyNullsMatchMissingValues() {
        var query = WaferLevelKpiQuery.build("lisa", request(Arrays.asList(null, null), List.of()), 10);

        assertThat(query.sql()).contains("les.product_id IS NULL").doesNotContain(":productIds");
        assertThat(query.parameters().hasValue("productIds")).isFalse();
    }

    @Test
    void mixedValuesAlsoMatchMissingValues() {
        var query = WaferLevelKpiQuery.build("lisa", request(Arrays.asList("AAA2", null), List.of()), 10);

        assertThat(query.sql()).contains("(les.product_id IN (:productIds) OR les.product_id IS NULL)");
        assertThat(query.parameters().getValue("productIds")).isEqualTo(List.of("AAA2"));
    }
}
