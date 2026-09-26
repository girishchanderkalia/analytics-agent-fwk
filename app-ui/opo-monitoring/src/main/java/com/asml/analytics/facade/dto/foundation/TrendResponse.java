package com.asml.analytics.facade.dto.foundation;
import java.util.List; import java.util.Map;
public record TrendResponse(List<Map<String,Object>> series, Map<String,Object> metadata) {}
