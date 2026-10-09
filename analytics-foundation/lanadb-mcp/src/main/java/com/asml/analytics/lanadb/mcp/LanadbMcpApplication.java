package com.asml.analytics.lanadb.mcp;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class LanadbMcpApplication {

    public static void main(String[] args) {
        SpringApplication.run(LanadbMcpApplication.class, args);
    }
}
