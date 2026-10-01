package com.asml.analytics.facade.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import com.asml.analytics.facade.client.AnalyticsFoundationClient;
import com.asml.analytics.facade.dto.foundation.TrendQuery;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class OpoAgentServiceTest {

    @Test
    void normalizesInclusiveCalendarMonthAndPreservesFilters() {
        AnalyticsFoundationClient client = mock(AnalyticsFoundationClient.class);
        OpoAgentService service = new OpoAgentService(client);

        TrendQuery normalized = service.normalizeTrendWindow(new TrendQuery(
                Map.of(
                        "start_date", "2026-08-17",
                        "end_date", "2099-01-01",
                        "product_ids", List.of("AAA2"),
                        "chuck_ids", List.of("Waferstage chuck ID 1")),
                List.of("machine")));

        assertEquals("2026-08-17", normalized.filters().get("start_date"));
        assertEquals("2026-09-16", normalized.filters().get("end_date"));
        assertEquals(List.of("AAA2"), normalized.filters().get("product_ids"));
        assertEquals(List.of("Waferstage chuck ID 1"), normalized.filters().get("chuck_ids"));
        assertEquals(List.of("machine"), normalized.groupBy());
    }

    @Test
    void chartQueryDelegatesOnlyToFoundationWithNormalizedFilters() {
        AnalyticsFoundationClient client = mock(AnalyticsFoundationClient.class);
        OpoAgentService service = new OpoAgentService(client);
        TrendQuery request = new TrendQuery(Map.of("start_date", "2026-12-17"), List.of());
        Map<String, Object> expectedFilters = new java.util.LinkedHashMap<>();
        expectedFilters.put("start_date", "2026-12-17");
        expectedFilters.put("end_date", "2027-01-16");
        expectedFilters.put("lookback_days", null);

        service.queryTrends(request);

        verify(client).queryTrends(new TrendQuery(expectedFilters, new ArrayList<>()));
    }
}