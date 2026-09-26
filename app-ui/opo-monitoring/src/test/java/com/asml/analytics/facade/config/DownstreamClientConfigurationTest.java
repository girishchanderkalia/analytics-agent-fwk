package com.asml.analytics.facade.config;
import static org.assertj.core.api.Assertions.assertThat;
import com.asml.analytics.facade.client.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
@SpringBootTest(properties={"downstream.runtime-service.base-url=http://127.0.0.1:8000","downstream.analytics-foundation.base-url=http://127.0.0.1:8200"})
class DownstreamClientConfigurationTest {
 @Autowired RuntimeServiceClient runtime;
 @Autowired AnalyticsFoundationClient foundation;
 @Test void createsExactlyTheTwoTypedClients(){ assertThat(runtime).isInstanceOf(HttpRuntimeServiceClient.class); assertThat(foundation).isInstanceOf(HttpAnalyticsFoundationClient.class); }
}
