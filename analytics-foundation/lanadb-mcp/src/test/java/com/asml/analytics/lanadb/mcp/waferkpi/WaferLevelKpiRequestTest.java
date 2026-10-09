package com.asml.analytics.lanadb.mcp.waferkpi;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.OffsetDateTime;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class WaferLevelKpiRequestTest {

    private static Map<String, Object> window() {
        var arguments = new HashMap<String, Object>();
        arguments.put("lotExposureStartFrom", "2024-09-01T00:00:00Z");
        arguments.put("lotExposureStartTo", "2024-09-17T23:59:59+02:00");
        return arguments;
    }

    @Test
    void parsesWindowAndDefaultsListsToEmpty() {
        var request = WaferLevelKpiRequest.fromArguments(window());

        assertThat(request.lotExposureStartFrom()).isEqualTo(OffsetDateTime.parse("2024-09-01T00:00:00Z"));
        assertThat(request.lotExposureStartTo()).isEqualTo(OffsetDateTime.parse("2024-09-17T23:59:59+02:00"));
        assertThat(request.productIds()).isEmpty();
        assertThat(request.chuckIds()).isEmpty();
    }

    @Test
    void keepsNullElementsInIdLists() {
        var arguments = window();
        arguments.put("productIds", Arrays.asList("AAA2", null));

        assertThat(WaferLevelKpiRequest.fromArguments(arguments).productIds()).containsExactly("AAA2", null);
    }

    @Test
    void rejectsUnknownArguments() {
        var arguments = window();
        arguments.put("sql", "DROP TABLE x");

        assertThatThrownBy(() -> WaferLevelKpiRequest.fromArguments(arguments))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("sql");
    }

    @Test
    void rejectsMissingLowerBoundOrInvalidText() {
        var missing = window();
        missing.remove("lotExposureStartFrom");
        var invalid = window();
        invalid.put("lotExposureStartFrom", "since 17 Aug");

        assertThatThrownBy(() -> WaferLevelKpiRequest.fromArguments(missing))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> WaferLevelKpiRequest.fromArguments(invalid))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("lotExposureStartFrom");
    }

    @Test
    void datesCoverWholeUtcDays() {
        var arguments = window();
        arguments.put("lotExposureStartFrom", "2026-08-17");
        arguments.put("lotExposureStartTo", "2026-09-30");

        var request = WaferLevelKpiRequest.fromArguments(arguments);

        assertThat(request.lotExposureStartFrom()).isEqualTo(OffsetDateTime.parse("2026-08-17T00:00:00Z"));
        assertThat(request.lotExposureStartTo()).isEqualTo(OffsetDateTime.parse("2026-09-30T23:59:59.999999Z"));
    }

    @Test
    void missingUpperBoundIsOpenEnded() {
        var missing = window();
        missing.remove("lotExposureStartTo");
        var explicitNull = window();
        explicitNull.put("lotExposureStartTo", null);

        assertThat(WaferLevelKpiRequest.fromArguments(missing).lotExposureStartTo()).isNull();
        assertThat(WaferLevelKpiRequest.fromArguments(explicitNull).lotExposureStartTo()).isNull();
    }

    @Test
    void rejectsReversedWindow() {
        var arguments = window();
        arguments.put("lotExposureStartFrom", "2024-10-01T00:00:00Z");

        assertThatThrownBy(() -> WaferLevelKpiRequest.fromArguments(arguments))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("must not be after");
    }

    @Test
    void rejectsNonStringIds() {
        var arguments = window();
        arguments.put("lotIds", List.of(42));
        var scalar = window();
        scalar.put("layerIds", "OV_NO_ID2");

        assertThatThrownBy(() -> WaferLevelKpiRequest.fromArguments(arguments))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> WaferLevelKpiRequest.fromArguments(scalar))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
