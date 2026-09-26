package com.asml.analytics.facade;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
@SpringBootTest(properties={"downstream.runtime-service.base-url=http://127.0.0.1:8000","downstream.analytics-foundation.base-url=http://127.0.0.1:8200"})
class OpoMonitoringApplicationTest { @Test void contextLoads() {} }
