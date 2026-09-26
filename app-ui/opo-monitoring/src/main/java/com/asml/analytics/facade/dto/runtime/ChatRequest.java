package com.asml.analytics.facade.dto.runtime;
import jakarta.validation.constraints.NotBlank;
import java.util.Map;
public record ChatRequest(@NotBlank String agentId, String agentVersion, @NotBlank String message, String userId, Map<String,Object> applicationContext) {
    public ChatRequest { applicationContext = applicationContext == null ? Map.of() : Map.copyOf(applicationContext); }
}
