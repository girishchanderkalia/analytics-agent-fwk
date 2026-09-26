package com.asml.analytics.facade.controller;
import com.asml.analytics.facade.client.RuntimeServiceClient;
import com.asml.analytics.facade.dto.runtime.*;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/investigations")
public class InvestigationController {
    private final RuntimeServiceClient client;
    public InvestigationController(RuntimeServiceClient client) { this.client=client; }
    @PostMapping("/chat") public RuntimeResponse chat(@Valid @RequestBody ChatRequest request) { return client.chat(request); }
    @PostMapping("/{conversationId}/resume") public RuntimeResponse resume(@PathVariable String conversationId,@RequestBody ResumeRequest request) { return client.resume(conversationId,request); }
    @GetMapping("/{conversationId}") public RuntimeResponse get(@PathVariable String conversationId) { return client.getConversation(conversationId); }
}
