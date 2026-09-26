package com.asml.analytics.facade.dto.foundation;
import java.util.Map;
public record WaferQueryRequest(String workspaceId, String table, Map<String,Object> filters) {}
