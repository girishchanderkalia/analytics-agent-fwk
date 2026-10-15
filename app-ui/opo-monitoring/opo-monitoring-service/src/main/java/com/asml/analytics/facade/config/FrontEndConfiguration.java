package com.asml.analytics.facade.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.CacheControl;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.ViewControllerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/** Serves the opo-monitoring-fe assets so the UI shares the BFF origin. */
@Configuration(proxyBeanMethods = false)
public class FrontEndConfiguration implements WebMvcConfigurer {

    private final String staticLocation;

    public FrontEndConfiguration(
            @Value("${ui.static-location}") String staticLocation) {
        this.staticLocation = staticLocation.endsWith("/")
                ? staticLocation
                : staticLocation + "/";
    }

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        // Explicit no-store so index.html (served through this handler via the
        // "/" forward) can't be cached stale by an intermediate proxy either;
        // without it, only the asset requests happened to carry that header.
        registry.addResourceHandler("/static/**")
                .addResourceLocations(staticLocation)
                .setCacheControl(CacheControl.noStore().mustRevalidate());
    }

    @Override
    public void addViewControllers(ViewControllerRegistry registry) {
        registry.addViewController("/").setViewName("forward:/static/index.html");
    }
}
