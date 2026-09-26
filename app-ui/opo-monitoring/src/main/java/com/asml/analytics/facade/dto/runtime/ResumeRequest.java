package com.asml.analytics.facade.dto.runtime;
import java.util.Map;
public record ResumeRequest(boolean approved, String selectedOutlierId, String comment, Integer expectedVersion, Map<String,Object> values) {
    public ResumeRequest { values = values == null ? Map.of() : Map.copyOf(values); }
}
