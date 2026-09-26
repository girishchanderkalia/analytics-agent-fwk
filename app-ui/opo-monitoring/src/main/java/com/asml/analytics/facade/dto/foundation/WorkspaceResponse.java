package com.asml.analytics.facade.dto.foundation;
import java.util.Map;
public record WorkspaceResponse(String workspaceId, String status, Map<String,Object> details) {}
