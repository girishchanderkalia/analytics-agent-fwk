package com.asml.analytics.facade.client;
import static org.assertj.core.api.Assertions.assertThat;
import org.junit.jupiter.api.Test;
import org.springframework.stereotype.Component;
class NoComponentAnnotationTest {
 @Test void implementationsAreCreatedOnlyByConfiguration(){
  assertThat(HttpRuntimeServiceClient.class.isAnnotationPresent(Component.class)).isFalse();
  assertThat(HttpAnalyticsFoundationClient.class.isAnnotationPresent(Component.class)).isFalse();
 }
}
