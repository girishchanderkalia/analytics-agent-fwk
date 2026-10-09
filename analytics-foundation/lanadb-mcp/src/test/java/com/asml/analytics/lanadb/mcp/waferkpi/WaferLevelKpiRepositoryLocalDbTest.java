package com.asml.analytics.lanadb.mcp.waferkpi;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

/** Runs against the restored local LanaDB dump; enable with LANADB_IT=true. */
@SpringBootTest
@EnabledIfEnvironmentVariable(named = "LANADB_IT", matches = "true")
class WaferLevelKpiRepositoryLocalDbTest {

    private static final OffsetDateTime FROM = OffsetDateTime.parse("2000-01-01T00:00:00Z");
    private static final OffsetDateTime TO = OffsetDateTime.parse("2100-01-01T00:00:00Z");

    @Autowired
    private WaferLevelKpiRepository repository;

    private WaferLevelKpiResult query(List<String> productIds, List<String> chuckIds) {
        return repository.getWaferLevelKpis(
                new WaferLevelKpiRequest(FROM, TO, productIds, List.of(), List.of(), List.of(), chuckIds));
    }

    @Test
    void returnsRoundedKpisWithinWindow() {
        var result = query(List.of(), List.of());

        assertThat(result.rows()).isNotEmpty();
        assertThat(result.rowCount()).isEqualTo(result.rows().size());
        assertThat(result.rows()).anySatisfy(row -> assertThat(row.chuckId()).isNotBlank());
        assertThat(result.rows()).allSatisfy(row -> {
            assertThat(row.lotStart()).isBetween(FROM, TO);
            assertThat(Math.round(row.kpiValue1() * 100) / 100.0).isEqualTo(row.kpiValue1());
            assertThat(Math.round(row.kpiValue2() * 100) / 100.0).isEqualTo(row.kpiValue2());
        });
    }

    @Test
    void filtersByProductAndChuck() {
        var all = query(List.of(), List.of());
        String product = all.rows().get(0).productId();
        String chuck = all.rows().get(0).chuckId();

        var filtered = query(List.of(product), List.of(chuck));

        assertThat(filtered.rows()).isNotEmpty().allSatisfy(row -> {
            assertThat(row.productId()).isEqualTo(product);
            assertThat(row.chuckId()).isEqualTo(chuck);
        });
        assertThat(filtered.rowCount()).isLessThan(all.rowCount());
    }

    @Test
    void emptyWindowReturnsNoRows() {
        var result = repository.getWaferLevelKpis(new WaferLevelKpiRequest(
                OffsetDateTime.parse("1990-01-01T00:00:00Z"), OffsetDateTime.parse("1990-01-02T00:00:00Z"),
                List.of(), List.of(), List.of(), List.of(), List.of()));

        assertThat(result.rows()).isEmpty();
        assertThat(result.truncated()).isFalse();
    }
}
