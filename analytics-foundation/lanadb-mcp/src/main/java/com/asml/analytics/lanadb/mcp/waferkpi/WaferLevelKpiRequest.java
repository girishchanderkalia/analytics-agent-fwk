package com.asml.analytics.lanadb.mcp.waferkpi;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeParseException;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/**
 * Constraints for wafer level KPIs. A null upper bound leaves the window open-ended. For each id list:
 * empty means unrestricted, and a null element also matches rows where that column is null.
 */
public record WaferLevelKpiRequest(
        OffsetDateTime lotExposureStartFrom,
        OffsetDateTime lotExposureStartTo,
        List<String> productIds,
        List<String> layerIds,
        List<String> exposureEquipmentIds,
        List<String> lotIds,
        List<String> chuckIds) {

    static final String FROM = "lotExposureStartFrom";
    static final String TO = "lotExposureStartTo";
    static final String PRODUCT_IDS = "productIds";
    static final String LAYER_IDS = "layerIds";
    static final String EXPOSURE_EQUIPMENT_IDS = "exposureEquipmentIds";
    static final String LOT_IDS = "lotIds";
    static final String CHUCK_IDS = "chuckIds";

    private static final Set<String> ARGUMENTS =
            Set.of(FROM, TO, PRODUCT_IDS, LAYER_IDS, EXPOSURE_EQUIPMENT_IDS, LOT_IDS, CHUCK_IDS);

    public WaferLevelKpiRequest {
        if (lotExposureStartFrom == null) {
            throw new IllegalArgumentException(FROM + " is required");
        }
        if (lotExposureStartTo != null && lotExposureStartFrom.isAfter(lotExposureStartTo)) {
            throw new IllegalArgumentException(FROM + " must not be after " + TO);
        }
        productIds = immutable(productIds);
        layerIds = immutable(layerIds);
        exposureEquipmentIds = immutable(exposureEquipmentIds);
        lotIds = immutable(lotIds);
        chuckIds = immutable(chuckIds);
    }

    /** Validate untrusted MCP tool arguments. */
    public static WaferLevelKpiRequest fromArguments(Map<String, ?> arguments) {
        Set<String> unknown = new TreeSet<>(arguments.keySet());
        unknown.removeAll(ARGUMENTS);
        if (!unknown.isEmpty()) {
            throw new IllegalArgumentException("Unknown argument(s): " + String.join(", ", unknown));
        }
        return new WaferLevelKpiRequest(
                dateTime(arguments, FROM, false),
                dateTime(arguments, TO, true),
                ids(arguments, PRODUCT_IDS),
                ids(arguments, LAYER_IDS),
                ids(arguments, EXPOSURE_EQUIPMENT_IDS),
                ids(arguments, LOT_IDS),
                ids(arguments, CHUCK_IDS));
    }

    /** A plain ISO date covers the whole UTC day, so an upper bound date is inclusive. */
    private static OffsetDateTime dateTime(Map<String, ?> arguments, String name, boolean upperBound) {
        Object value = arguments.get(name);
        if (value == null && upperBound) {
            return null;
        }
        if (!(value instanceof String text) || text.isBlank()) {
            throw new IllegalArgumentException(name + " must be an ISO-8601 date or date-time string with offset");
        }
        String trimmed = text.strip();
        try {
            if (trimmed.length() == 10) {
                OffsetDateTime dayStart = LocalDate.parse(trimmed).atStartOfDay().atOffset(ZoneOffset.UTC);
                // timestamptz has microsecond precision, so this is the last instant of the day.
                return upperBound ? dayStart.plusDays(1).minus(1, ChronoUnit.MICROS) : dayStart;
            }
            return OffsetDateTime.parse(trimmed);
        } catch (DateTimeParseException exception) {
            throw new IllegalArgumentException(
                    name + " must be an ISO-8601 date or date-time with offset, e.g. 2024-09-01 or "
                            + "2024-09-01T00:00:00Z", exception);
        }
    }

    private static List<String> ids(Map<String, ?> arguments, String name) {
        Object value = arguments.get(name);
        if (value == null) {
            return List.of();
        }
        if (!(value instanceof List<?> items)) {
            throw new IllegalArgumentException(name + " must be an array of strings or nulls");
        }
        List<String> ids = new ArrayList<>(items.size());
        for (Object item : items) {
            if (item != null && !(item instanceof String)) {
                throw new IllegalArgumentException(name + " must be an array of strings or nulls");
            }
            ids.add((String) item);
        }
        return ids;
    }

    private static List<String> immutable(List<String> values) {
        return values == null ? List.of() : Collections.unmodifiableList(new ArrayList<>(values));
    }
}
