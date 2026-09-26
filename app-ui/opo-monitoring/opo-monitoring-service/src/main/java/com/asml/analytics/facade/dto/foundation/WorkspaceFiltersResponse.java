package com.asml.analytics.facade.dto.foundation;
import java.util.Map;
public record WorkspaceFiltersResponse(String workspaceId, Map<String,Object> filters) {}
