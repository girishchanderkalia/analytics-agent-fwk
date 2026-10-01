package com.asml.analytics.facade.client;

import com.asml.analytics.facade.dto.runtime.ChatRequest;
import com.asml.analytics.facade.dto.runtime.RegisteredAgentList;
import com.asml.analytics.facade.dto.runtime.ResumeRequest;
import com.asml.analytics.facade.dto.runtime.RuntimeResponse;
import java.util.concurrent.Callable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.client.RestClient;

public final class HttpRuntimeServiceClient implements RuntimeServiceClient {
    private static final Logger LOGGER = LoggerFactory.getLogger(HttpRuntimeServiceClient.class);
    private final RestClient client;

    public HttpRuntimeServiceClient(RestClient client) {
        this.client = client;
    }

    @Override
    public RuntimeResponse chat(ChatRequest request) {
        return call("chat", () -> client.post().uri("/v1/chat").body(request).retrieve().body(RuntimeResponse.class));
    }

    @Override
    public RuntimeResponse resume(String conversationId, ResumeRequest request) {
        return call("resume", () -> client.post().uri("/v1/conversations/{conversationId}/resume", conversationId).body(request).retrieve().body(RuntimeResponse.class));
    }

    @Override
    public RuntimeResponse getConversation(String conversationId) {
        return call("get_conversation", () -> client.get().uri("/v1/conversations/{conversationId}", conversationId).retrieve().body(RuntimeResponse.class));
    }

    @Override
    public RegisteredAgentList listAgents(String applicationId) {
        return call("list_agents", () -> client.get().uri("/v1/applications/{applicationId}/agents", applicationId).retrieve().body(RegisteredAgentList.class));
    }

    private <T> T call(String operation, Callable<T> action) {
        long started = System.nanoTime();
        try {
            T result = action.call();
            if (result == null) throw new IllegalStateException("Empty Runtime Service response");
            LOGGER.info("runtime_http_complete operation={} elapsed_ms={}", operation, (System.nanoTime() - started) / 1_000_000);
            return result;
        } catch (Exception error) {
            LOGGER.warn("runtime_http_failed operation={} elapsed_ms={}", operation, (System.nanoTime() - started) / 1_000_000, error);
            throw new DownstreamClientException("runtime-service", error);
        }
    }
}
