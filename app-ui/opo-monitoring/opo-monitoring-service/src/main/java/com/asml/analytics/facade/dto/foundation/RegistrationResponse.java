package com.asml.analytics.facade.dto.foundation;
public record RegistrationResponse(String registrationId, String workspaceId, String status, int progressPct, String table, String error) {}
