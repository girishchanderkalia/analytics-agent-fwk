package com.asml.analytics.facade.dto.foundation;
import java.util.List; import java.util.Map;
public record WaferQueryResponse(String workspaceId, String table, List<Map<String,Object>> rows, List<String> anomalousWafers) {}
