package com.asml.analytics.facade.client;

import com.asml.analytics.facade.dto.runtime.ChatRequest;
import com.asml.analytics.facade.dto.runtime.ResumeRequest;
import com.asml.analytics.facade.dto.runtime.RuntimeResponse;
import java.util.concurrent.Callable;
import org.springframework.web.client.RestClient;

public final class HttpRuntimeServiceClient implements RuntimeServiceClient {
    private final RestClient client;

    public HttpRuntimeServiceClient(RestClient client) {
        this.client = client;
    }

    @Override
    public RuntimeResponse chat(ChatRequest request) {
        return call(() -> client.post().uri("/v1/chat").body(request).retrieve().body(RuntimeResponse.class));
    }

    @Override
    public RuntimeResponse resume(String conversationId, ResumeRequest request) {
        return call(() -> client.post().uri("/v1/conversations/{conversationId}/resume", conversationId).body(request).retrieve().body(RuntimeResponse.class));
    }

    @Override
    public RuntimeResponse getConversation(String conversationId) {
        return call(() -> client.get().uri("/v1/conversations/{conversationId}", conversationId).retrieve().body(RuntimeResponse.class));
    }

    private <T> T call(Callable<T> action) {
        try {
            T result = action.call();
            if (result == null) throw new IllegalStateException("Empty Runtime Service response");
            return result;
        } catch (Exception error) {
            throw new DownstreamClientException("runtime-service", error);
        }
    }
}
