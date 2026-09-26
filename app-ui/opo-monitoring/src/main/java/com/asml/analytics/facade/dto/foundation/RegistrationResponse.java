package com.asml.analytics.facade.dto.foundation;
import java.util.Map;
public record RegistrationResponse(String registrationId, String workspaceId, String status, Map<String,Object> details) {}
