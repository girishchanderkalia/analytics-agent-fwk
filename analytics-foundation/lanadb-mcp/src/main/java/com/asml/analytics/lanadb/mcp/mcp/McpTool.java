package com.asml.analytics.lanadb.mcp.mcp;

import java.util.Map;

/** A tool published over MCP; every Spring bean implementing this is discoverable. */
public interface McpTool {

    String name();

    String description();

    Map<String, Object> inputSchema();

    Map<String, Object> outputSchema();

    Map<String, Object> annotations();

    /** @throws IllegalArgumentException when the arguments are invalid */
    Object call(Map<String, Object> arguments);
}
