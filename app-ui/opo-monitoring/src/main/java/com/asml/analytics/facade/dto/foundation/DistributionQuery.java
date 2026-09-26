package com.asml.analytics.facade.dto.foundation;
import java.util.Map;
public record DistributionQuery(Map<String,Object> filters, String metric) {}
