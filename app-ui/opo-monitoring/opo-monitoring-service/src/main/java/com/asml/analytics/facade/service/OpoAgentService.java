package com.asml.analytics.facade.service;

import com.asml.analytics.facade.client.AnalyticsFoundationClient;
import com.asml.analytics.facade.dto.foundation.DistributionQuery;
import com.asml.analytics.facade.dto.foundation.DistributionResponse;
import com.asml.analytics.facade.dto.foundation.TrendQuery;
import com.asml.analytics.facade.dto.foundation.TrendResponse;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.stereotype.Service;

/** Internal application-owned orchestration for deterministic OPO chart work. */
@Service
public class OpoAgentService {

    private final AnalyticsFoundationClient foundationClient;

    public OpoAgentService(AnalyticsFoundationClient foundationClient) {
        this.foundationClient = foundationClient;
    }

    public TrendResponse queryTrends(TrendQuery request) {
        return foundationClient.queryTrends(normalizeTrendWindow(request));
    }

    public DistributionResponse getDistribution(DistributionQuery request) {
        return foundationClient.getDistribution(request);
    }

    public TrendQuery normalizeTrendWindow(TrendQuery request) {
        if (request == null || request.filters() == null) {
            return request;
        }

        Map<String, Object> filters = new LinkedHashMap<>(request.filters());
        Object startValue = filters.get("start_date");
        if (startValue == null || startValue.toString().isBlank()) {
            filters.put("end_date", null);
            return new TrendQuery(filters, request.groupBy());
        }

        LocalDate start = LocalDate.parse(startValue.toString());
        filters.put("start_date", start.toString());
        filters.put("end_date", start.plusMonths(1).minusDays(1).toString());
        filters.put("lookback_days", null);
        return new TrendQuery(filters, request.groupBy());
    }
}