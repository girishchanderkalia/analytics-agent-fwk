package com.asml.analytics.facade.client;

import com.asml.analytics.facade.dto.runtime.ChatRequest;
import com.asml.analytics.facade.dto.runtime.ResumeRequest;
import com.asml.analytics.facade.dto.runtime.RuntimeResponse;

public interface RuntimeServiceClient {
    RuntimeResponse chat(ChatRequest request);
    RuntimeResponse resume(String conversationId, ResumeRequest request);
    RuntimeResponse getConversation(String conversationId);
}
