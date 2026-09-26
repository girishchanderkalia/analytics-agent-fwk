package com.asml.analytics.facade.dto.foundation;
import java.util.Map;
public record RegistrationRequest(String datasetName, Map<String,Object> options) {}
