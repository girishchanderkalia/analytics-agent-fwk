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
        registry.addResourceHandler("/static/**")
            .addResourceLocations(staticLocation)
            .setCacheControl(CacheControl.noCache());
    }

    @Override
    public void addViewControllers(ViewControllerRegistry registry) {
        registry.addViewController("/").setViewName("forward:/static/index.html");
        registry.addViewController("/overlay").setViewName("forward:/static/overlay.html");
    }
}
