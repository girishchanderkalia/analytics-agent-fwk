package com.asml.analytics.facade.config;

import com.asml.analytics.facade.client.AnalyticsFoundationClient;
import com.asml.analytics.facade.client.HttpAnalyticsFoundationClient;
import com.asml.analytics.facade.client.HttpRuntimeServiceClient;
import com.asml.analytics.facade.client.RuntimeServiceClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;
import org.springframework.http.client.SimpleClientHttpRequestFactory;

@Configuration(proxyBeanMethods = false)
public class DownstreamClientConfiguration {

        @Bean
        RuntimeServiceClient runtimeServiceClient(
                        RestClient.Builder builder,
                        @Value("${downstream.runtime-service.base-url}") String baseUrl) {

                RestClient client = builder
                                .clone()
                                .baseUrl(baseUrl)
                                .build();

                return new HttpRuntimeServiceClient(client);
        }

        @Bean
        AnalyticsFoundationClient analyticsFoundationClient(
                        RestClient.Builder builder,
                        @Value("${downstream.analytics-foundation.base-url}") String baseUrl) {

                SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();

                requestFactory.setConnectTimeout(5_000);
                requestFactory.setReadTimeout(60_000);

                RestClient client = builder
                                .clone()
                                .baseUrl(baseUrl)
                                .requestFactory(requestFactory)
                                .build();

                return new HttpAnalyticsFoundationClient(client);
        }
}
