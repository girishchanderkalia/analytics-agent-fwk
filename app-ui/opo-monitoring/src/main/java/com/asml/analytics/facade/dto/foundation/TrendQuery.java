package com.asml.analytics.facade.dto.foundation;
import java.util.List; import java.util.Map;
public record TrendQuery(Map<String,Object> filters, List<String> groupBy) {}
