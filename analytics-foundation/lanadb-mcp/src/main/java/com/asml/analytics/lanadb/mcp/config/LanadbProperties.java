package com.asml.analytics.lanadb.mcp.config;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * @param schema  PostgreSQL schema holding the LanaDB tables; restricted so it can be safely embedded in SQL
 * @param maxRows upper bound on rows returned by one tool call
 */
@Validated
@ConfigurationProperties("lanadb")
public record LanadbProperties(
        @NotBlank @Pattern(regexp = "[a-z_][a-z0-9_]*") String schema,
        @Min(1) @Max(100_000) int maxRows) {
}
