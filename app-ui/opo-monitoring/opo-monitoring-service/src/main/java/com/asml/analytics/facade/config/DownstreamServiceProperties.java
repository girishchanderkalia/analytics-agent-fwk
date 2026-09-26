package com.asml.analytics.facade.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "downstream")
public record DownstreamServiceProperties(
        Service runtimeService,
        Service analyticsFoundation) {

    public DownstreamServiceProperties {
        if (runtimeService == null) {
            throw new IllegalArgumentException("downstream.runtime-service is required");
        }
        if (analyticsFoundation == null) {
            throw new IllegalArgumentException("downstream.analytics-foundation is required");
        }
    }

    public record Service(String baseUrl) {
        public Service {
            if (baseUrl == null || baseUrl.isBlank()) {
                throw new IllegalArgumentException("Downstream base URL is required");
            }
        }
    }
}
