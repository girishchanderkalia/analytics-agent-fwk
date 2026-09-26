package com.asml.analytics.facade.dto.foundation;
import java.util.Map;
public record ConnectionInfoResponse(String workspaceId, Map<String,Object> connectionInfo) {}
