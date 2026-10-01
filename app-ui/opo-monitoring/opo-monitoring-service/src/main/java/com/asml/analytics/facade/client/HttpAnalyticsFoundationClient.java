package com.asml.analytics.facade.client;

import com.asml.analytics.facade.dto.foundation.ApplyFiltersRequest;
import com.asml.analytics.facade.dto.foundation.ConnectionInfoResponse;
import com.asml.analytics.facade.dto.foundation.CreateWorkspaceRequest;
import com.asml.analytics.facade.dto.foundation.DistributionQuery;
import com.asml.analytics.facade.dto.foundation.DistributionResponse;
import com.asml.analytics.facade.dto.foundation.RegistrationRequest;
import com.asml.analytics.facade.dto.foundation.RegistrationResponse;
import com.asml.analytics.facade.dto.foundation.TrendQuery;
import com.asml.analytics.facade.dto.foundation.TrendResponse;
import com.asml.analytics.facade.dto.foundation.WaferQueryRequest;
import com.asml.analytics.facade.dto.foundation.WaferQueryResponse;
import com.asml.analytics.facade.dto.foundation.WorkspaceFiltersResponse;
import com.asml.analytics.facade.dto.foundation.WorkspaceResponse;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.web.client.RestClient;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.http.MediaType;

public final class HttpAnalyticsFoundationClient
        implements AnalyticsFoundationClient {

    private static final Logger LOGGER = LoggerFactory.getLogger(
            HttpAnalyticsFoundationClient.class);

    private static final ParameterizedTypeReference<Map<String, Object>> MAP_RESPONSE = new ParameterizedTypeReference<>() {
    };

    private final RestClient client;

    public HttpAnalyticsFoundationClient(
            RestClient client) {
        this.client = client;
    }

    @Override
    public TrendResponse queryTrends(
            TrendQuery request) {

        Map<String, Object> foundationRequest = toFoundationTrendRequest(
                request == null
                        ? null
                        : request.filters());

        LOGGER.info(
                "Foundation trend query request: {}",
                foundationRequest);

        Map<String, Object> response = call(
                () -> client
                        .post()
                        .uri("/trends/query")
                        .contentType(
                                MediaType.APPLICATION_JSON)
                        .accept(
                                MediaType.APPLICATION_JSON)
                        .body(foundationRequest)
                        .retrieve()
                        .body(MAP_RESPONSE));

        return new TrendResponse(
                mapList(response.get("series")),
                mapValue(response.get("metadata")));
    }

    @Override
    public DistributionResponse getDistribution(
            DistributionQuery request) {

        Map<String, Object> foundationRequest = toFoundationTrendRequest(
                request == null
                        ? null
                        : request.filters());

        LOGGER.info(
                "Foundation distribution request: {}",
                foundationRequest);

        Map<String, Object> response = call(
                () -> client
                        .post()
                        .uri("/trends/distribution")
                        .contentType(
                                MediaType.APPLICATION_JSON)
                        .accept(
                                MediaType.APPLICATION_JSON)
                        .body(foundationRequest)
                        .retrieve()
                        .body(MAP_RESPONSE));

        Map<String, Object> quantiles = new LinkedHashMap<>();

        quantiles.put("p95", response.get("p95"));
        quantiles.put("p99", response.get("p99"));
        quantiles.put("stdev", response.get("stdev"));
        quantiles.put(
                "bell_curve_range",
                response.get("bell_curve_range"));

        return new DistributionResponse(
                longValue(response.get("sample_count")),
                null,
                null,
                doubleValue(response.get("mean")),
                quantiles);
    }

    @Override
    public WorkspaceResponse createWorkspace(
            CreateWorkspaceRequest request) {

        Map<String, Object> response = call(
                () -> client
                        .post()
                        .uri("/workspaces")
                        .accept(
                                MediaType.APPLICATION_JSON)
                        .retrieve()
                        .body(MAP_RESPONSE));

        return new WorkspaceResponse(
                stringValue(
                        response.get("workspace_id")));
    }

    @Override
    public WorkspaceFiltersResponse applyFilters(
            String workspaceId,
            ApplyFiltersRequest request) {

        Map<String, Object> foundationRequest = Map.of(
                "filters",
                request == null || request.filters() == null
                        ? Map.of()
                        : request.filters());

        Map<String, Object> response = call(
                () -> client
                        .post()
                        .uri(
                                "/workspaces/{workspaceId}/filters",
                                workspaceId)
                        .contentType(
                                MediaType.APPLICATION_JSON)
                        .accept(
                                MediaType.APPLICATION_JSON)
                        .body(foundationRequest)
                        .retrieve()
                        .body(MAP_RESPONSE));

        return new WorkspaceFiltersResponse(
                stringValue(
                        response.get("workspace_id")),
                mapValue(response.get("filters")));
    }

    @Override
    public ConnectionInfoResponse getConnectionInfo(
            String workspaceId) {

        Map<String, Object> response = call(
                () -> client
                        .get()
                        .uri(
                                "/workspaces/{workspaceId}/connection-info",
                                workspaceId)
                        .accept(
                                MediaType.APPLICATION_JSON)
                        .retrieve()
                        .body(MAP_RESPONSE));

        return new ConnectionInfoResponse(
                stringValue(
                        response.get("workspace_id")),
                mapValue(response.get("values")));
    }

    @Override
    public RegistrationResponse registerDataset(
            String workspaceId,
            RegistrationRequest request) {

        Map<String, Object> foundationRequest = new LinkedHashMap<>();

        foundationRequest.put(
                "dataset",
                request.dataset());
        foundationRequest.put(
                "table",
                request.table());

        Map<String, Object> response = call(
                () -> client
                        .post()
                        .uri(
                                "/workspaces/{workspaceId}/registrations",
                                workspaceId)
                        .contentType(
                                MediaType.APPLICATION_JSON)
                        .accept(
                                MediaType.APPLICATION_JSON)
                        .body(foundationRequest)
                        .retrieve()
                        .body(MAP_RESPONSE));

        return toRegistrationResponse(response);
    }

    @Override
    public RegistrationResponse getRegistration(
            String workspaceId,
            String registrationId) {

        Map<String, Object> response = call(
                () -> client
                        .get()
                        .uri(
                                "/workspaces/{workspaceId}/registrations/"
                                        + "{registrationId}",
                                workspaceId,
                                registrationId)
                        .accept(
                                MediaType.APPLICATION_JSON)
                        .retrieve()
                        .body(MAP_RESPONSE));

        return toRegistrationResponse(response);
    }

    @Override
    public WaferQueryResponse queryWafers(
            WaferQueryRequest request) {

        Map<String, Object> foundationRequest = new LinkedHashMap<>();

        foundationRequest.put(
                "workspace_id",
                request.workspaceId());
        foundationRequest.put(
                "table",
                request.table());
        foundationRequest.put(
                "filters",
                request.filters() == null
                        ? Map.of()
                        : request.filters());

        Map<String, Object> response = call(
                () -> client
                        .post()
                        .uri("/wafers/query")
                        .contentType(
                                MediaType.APPLICATION_JSON)
                        .accept(
                                MediaType.APPLICATION_JSON)
                        .body(foundationRequest)
                        .retrieve()
                        .body(MAP_RESPONSE));

        return new WaferQueryResponse(
                stringValue(
                        response.get("workspace_id")),
                stringValue(response.get("table")),
                mapList(response.get("rows")),
                stringList(
                        response,
                        "anomalous_wafers"));
    }

    private static RegistrationResponse toRegistrationResponse(
            Map<String, Object> response) {

        return new RegistrationResponse(
                stringValue(
                        response.get("registration_id")),
                stringValue(
                        response.get("workspace_id")),
                stringValue(response.get("status")),
                (int) longValue(
                        response.get("progress_pct")),
                stringValue(response.get("table")),
                stringValue(response.get("error")));
    }

    private static Map<String, Object> toFoundationTrendRequest(
            Map<String, Object> filters) {

        Map<String, Object> source = filters == null
                ? Map.of()
                : filters;

        Map<String, Object> target = new LinkedHashMap<>();

        putIfPresent(
                target,
                "days",
                firstPresent(source, "days"));

        putIfPresent(
                target,
                "start_date",
                firstPresent(
                        source,
                        "start_date",
                        "startDate"));

        putIfPresent(
                target,
                "end_date",
                firstPresent(
                        source,
                        "end_date",
                        "endDate"));

        target.put(
                "lot_ids",
                stringList(
                        source,
                        "lot_ids",
                        "lotIds"));

        target.put(
                "product_ids",
                stringList(
                        source,
                        "product_ids",
                        "productIds"));

        target.put(
                "layer_ids",
                stringList(
                        source,
                        "layer_ids",
                        "layerIds"));

        target.put(
                "exposure_equipment_ids",
                stringList(
                        source,
                        "exposure_equipment_ids",
                        "exposureEquipmentIds"));

        target.put(
                "chuck_ids",
                stringList(
                        source,
                        "chuck_ids",
                        "chuckIds"));

        return target;
    }

    private static Object firstPresent(
            Map<String, Object> source,
            String... keys) {

        for (String key : keys) {
            if (source.containsKey(key)) {
                return source.get(key);
            }
        }

        return null;
    }

    private static void putIfPresent(
            Map<String, Object> target,
            String key,
            Object value) {

        if (value != null) {
            target.put(key, value);
        }
    }

    private static List<String> stringList(
            Map<String, Object> source,
            String... keys) {

        Object value = firstPresent(source, keys);

        if (!(value instanceof List<?> values)) {
            return List.of();
        }

        return values.stream()
                .filter(item -> item != null)
                .map(Object::toString)
                .toList();
    }

    private static long longValue(
            Object value) {

        return value instanceof Number number
                ? number.longValue()
                : 0L;
    }

    private static String stringValue(
            Object value) {

        return value == null
                ? null
                : value.toString();
    }

    private static Double doubleValue(
            Object value) {

        return value instanceof Number number
                ? number.doubleValue()
                : null;
    }

    private static Map<String, Object> mapValue(
            Object value) {

        if (!(value instanceof Map<?, ?> source)) {
            return Map.of();
        }

        Map<String, Object> target = new LinkedHashMap<>();

        source.forEach(
                (key, item) -> {
                    if (key != null) {
                        target.put(
                                key.toString(),
                                item);
                    }
                });

        return target;
    }

    private static List<Map<String, Object>> mapList(
            Object value) {

        if (!(value instanceof List<?> source)) {
            return List.of();
        }

        return source.stream()
                .filter(Map.class::isInstance)
                .map(HttpAnalyticsFoundationClient::mapValue)
                .toList();
    }

    private <T> T call(
            Callable<T> action) {

        try {
            T result = action.call();

            if (result == null) {
                throw new IllegalStateException(
                        "Empty Analytics Foundation response");
            }

            return result;
        } catch (RestClientResponseException error) {
            LOGGER.error(
                    "Analytics Foundation returned HTTP {} with body: {}",
                    error.getStatusCode(),
                    error.getResponseBodyAsString(),
                    error);

            throw new DownstreamClientException(
                    "analytics-foundation",
                    error);
        } catch (Exception error) {
            LOGGER.error(
                    "Analytics Foundation call failed",
                    error);

            throw new DownstreamClientException(
                    "analytics-foundation",
                    error);
        }
    }

}
