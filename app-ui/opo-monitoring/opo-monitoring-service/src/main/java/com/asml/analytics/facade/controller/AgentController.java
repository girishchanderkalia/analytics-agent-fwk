package com.asml.analytics.facade.controller;
import com.asml.analytics.facade.client.RuntimeServiceClient;
import com.asml.analytics.facade.dto.runtime.RegisteredAgentList;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/applications/{applicationId}/agents")
public class AgentController {
    private final RuntimeServiceClient client;
    public AgentController(RuntimeServiceClient client) { this.client=client; }
    @GetMapping public RegisteredAgentList list(@PathVariable String applicationId) { return client.listAgents(applicationId); }
}
