package com.asml.analytics.lanadb.mcp.waferkpi;

import com.asml.analytics.lanadb.mcp.mcp.McpTool;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class WaferLevelKpiTool implements McpTool {

    private static final TypeReference<Map<String, Object>> OBJECT = new TypeReference<>() { };

    private final WaferLevelKpiRepository repository;
    private final Map<String, Object> inputSchema;
    private final Map<String, Object> outputSchema;

    public WaferLevelKpiTool(WaferLevelKpiRepository repository, ObjectMapper objectMapper) {
        this.repository = repository;
        this.inputSchema = schema(objectMapper, "getWaferLevelKpis.input.json");
        this.outputSchema = schema(objectMapper, "getWaferLevelKpis.output.json");
    }

    @Override
    public String name() {
        return "getWaferLevelKpis";
    }

    @Override
    public String description() {
        return "Wafer level overlay KPIs from LanaDB: raw M3S X/Y (nm, two decimals) per wafer measurement, "
                + "with product, lot, layer, wafer, chuck, exposure and measurement equipment, "
                + "filtered by lot exposure start window and optional id lists.";
    }

    @Override
    public Map<String, Object> inputSchema() {
        return inputSchema;
    }

    @Override
    public Map<String, Object> outputSchema() {
        return outputSchema;
    }

    @Override
    public Map<String, Object> annotations() {
        return Map.of("readOnlyHint", true, "idempotentHint", true);
    }

    @Override
    public WaferLevelKpiResult call(Map<String, Object> arguments) {
        return repository.getWaferLevelKpis(WaferLevelKpiRequest.fromArguments(arguments));
    }

    private static Map<String, Object> schema(ObjectMapper objectMapper, String file) {
        try (InputStream stream = WaferLevelKpiTool.class.getResourceAsStream("/mcp-tools/" + file)) {
            if (stream == null) {
                throw new IllegalStateException("Missing MCP tool schema: " + file);
            }
            return Map.copyOf(objectMapper.readValue(stream, OBJECT));
        } catch (IOException exception) {
            throw new UncheckedIOException(exception);
        }
    }
}
