package com.asml.analytics.facade.dto.foundation;
import java.util.Map;
public record DistributionResponse(long count, Double minimum, Double maximum, Double mean, Map<String,Object> quantiles) {}
