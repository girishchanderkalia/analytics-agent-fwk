package com.asml.analytics.facade.dto.foundation;
import java.util.List; import java.util.Map;
public record WaferQueryResponse(List<Map<String,Object>> rows, Map<String,Object> metadata) {}
