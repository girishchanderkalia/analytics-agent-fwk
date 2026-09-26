package com.asml.analytics.facade.dto.foundation;
import java.util.Map;
public record CreateWorkspaceRequest(String name, Map<String,Object> context) {}
