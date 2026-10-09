package com.asml.analytics.lanadb.mcp.mcp;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/** MCP over HTTP JSON-RPC, matching the protocol the agent runtime's MCP client speaks. */
@RestController
public class McpController {

    private static final Logger LOGGER = LoggerFactory.getLogger(McpController.class);
    private static final TypeReference<Map<String, Object>> OBJECT = new TypeReference<>() { };

    private final Map<String, McpTool> tools;
    private final ObjectMapper objectMapper;

    public McpController(List<McpTool> tools, ObjectMapper objectMapper) {
        this.tools = tools.stream().collect(Collectors.toMap(
                McpTool::name, Function.identity(), (left, right) -> {
                    throw new IllegalStateException("Duplicate MCP tool: " + left.name());
                }, LinkedHashMap::new));
        this.objectMapper = objectMapper;
    }

    @PostMapping(path = "/mcp", consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> handle(@RequestBody Map<String, Object> request) {
        Object id = request.get("id");
        if (!"2.0".equals(request.get("jsonrpc"))) {
            return error(id, -32600, "Invalid JSON-RPC request");
        }
        Object method = request.get("method");
        if ("tools/list".equals(method)) {
            return result(id, Map.of("tools", tools.values().stream().map(McpController::descriptor).toList()));
        }
        if ("tools/call".equals(method)) {
            return call(id, request.get("params"));
        }
        return error(id, -32601, "Method not found");
    }

    private Map<String, Object> call(Object id, Object params) {
        if (!(params instanceof Map<?, ?> values)) {
            return error(id, -32602, "params must be an object");
        }
        if (!(values.get("name") instanceof String name) || name.isBlank()) {
            return error(id, -32602, "tool name is required");
        }
        McpTool tool = tools.get(name);
        if (tool == null) {
            return error(id, -32602, "Unknown LanaDB MCP tool: " + name);
        }
        Object arguments = values.get("arguments");
        if (arguments != null && !(arguments instanceof Map)) {
            return error(id, -32602, "tool arguments must be an object");
        }
        try {
            Map<String, Object> structured = objectMapper.convertValue(
                    tool.call(arguments == null ? Map.of() : objectMapper.convertValue(arguments, OBJECT)), OBJECT);
            Map<String, Object> content = Map.of("type", "text", "text", objectMapper.writeValueAsString(structured));
            return result(id, Map.of("content", List.of(content), "structuredContent", structured, "isError", false));
        } catch (IllegalArgumentException exception) {
            return error(id, -32602, exception.getMessage());
        } catch (DataAccessException | JsonProcessingException exception) {
            // Details stay in the server log; they can contain SQL and connection information.
            LOGGER.error("MCP tool {} failed", name, exception);
            return error(id, -32000, "LanaDB tool " + name + " failed");
        }
    }

    private static Map<String, Object> descriptor(McpTool tool) {
        return Map.of(
                "name", tool.name(),
                "description", tool.description(),
                "inputSchema", tool.inputSchema(),
                "outputSchema", tool.outputSchema(),
                "annotations", tool.annotations());
    }

    private static Map<String, Object> result(Object id, Map<String, Object> result) {
        var response = new LinkedHashMap<String, Object>();
        response.put("jsonrpc", "2.0");
        response.put("id", id);
        response.put("result", result);
        return response;
    }

    private static Map<String, Object> error(Object id, int code, String message) {
        var response = new LinkedHashMap<String, Object>();
        response.put("jsonrpc", "2.0");
        response.put("id", id);
        response.put("error", Map.of("code", code, "message", message));
        return response;
    }
}
