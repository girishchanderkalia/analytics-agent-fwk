package com.asml.analytics.facade.controller;

import com.asml.analytics.facade.client.AnalyticsFoundationClient;
import com.asml.analytics.facade.client.RuntimeServiceClient;
import com.asml.analytics.facade.dto.foundation.TrendQuery;
import com.asml.analytics.facade.dto.runtime.*;
import jakarta.validation.Valid;
import java.util.Map;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/investigations")
public class InvestigationController {
    private static final String TREND_EVIDENCE_APPROVAL_ID = "request_trend_evidence";

    private final RuntimeServiceClient client;
    private final AnalyticsFoundationClient foundationClient;

    public InvestigationController(RuntimeServiceClient client, AnalyticsFoundationClient foundationClient) {
        this.client = client;
        this.foundationClient = foundationClient;
    }

    @PostMapping("/chat")
    public RuntimeResponse chat(@Valid @RequestBody ChatRequest request) {
        return resolveTrendEvidence(client.chat(request));
    }

    @PostMapping("/{conversationId}/resume")
    public RuntimeResponse resume(@PathVariable String conversationId, @RequestBody ResumeRequest request) {
        return resolveTrendEvidence(client.resume(conversationId, request));
    }

    @GetMapping("/{conversationId}")
    public RuntimeResponse get(@PathVariable String conversationId) {
        return client.getConversation(conversationId);
    }

    // The runtime pauses right after parsing trend filters so the application can
    // supply
    // Foundation trend evidence itself, resolved here instead of surfacing it to
    // the analyst.
    private RuntimeResponse resolveTrendEvidence(RuntimeResponse response) {
        Map<String, Object> approvalRequest = response.approvalRequest();
        if (approvalRequest == null || !TREND_EVIDENCE_APPROVAL_ID.equals(approvalRequest.get("approval_id"))) {
            return response;
        }

        @SuppressWarnings("unchecked")
        Map<String, Object> payload = (Map<String, Object>) approvalRequest.get("payload");
        @SuppressWarnings("unchecked")
        Map<String, Object> trendFilters = payload == null ? Map.of()
                : (Map<String, Object>) payload.get("trend_filters");

        var trendSeries = foundationClient.queryTrends(new TrendQuery(trendFilters, null)).series();

        return resolveTrendEvidence(client.resume(
                response.conversationId(),
                new ResumeRequest(true, null, null, response.version(), Map.of("trend_series", trendSeries))));
    }
}
