package com.asml.analytics.facade.dto.runtime;
import java.util.Map;
public record RuntimeResponse(String conversationId, String agentId, String agentVersion, String status, int version, Map<String,Object> result, Map<String,Object> approvalRequest) {}
