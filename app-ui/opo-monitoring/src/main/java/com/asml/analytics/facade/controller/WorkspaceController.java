package com.asml.analytics.facade.controller;
import com.asml.analytics.facade.client.AnalyticsFoundationClient;
import com.asml.analytics.facade.dto.foundation.*;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/workspaces")
public class WorkspaceController {
    private final AnalyticsFoundationClient client;
    public WorkspaceController(AnalyticsFoundationClient client){this.client=client;}
    @PostMapping public WorkspaceResponse create(@RequestBody CreateWorkspaceRequest request){return client.createWorkspace(request);}
    @PostMapping("/{workspaceId}/filters") public WorkspaceResponse filters(@PathVariable String workspaceId,@RequestBody ApplyFiltersRequest request){return client.applyFilters(workspaceId,request);}
    @GetMapping("/{workspaceId}/connection-info") public ConnectionInfoResponse connection(@PathVariable String workspaceId){return client.getConnectionInfo(workspaceId);}
    @PostMapping("/{workspaceId}/registrations") public RegistrationResponse register(@PathVariable String workspaceId,@RequestBody RegistrationRequest request){return client.registerDataset(workspaceId,request);}
    @GetMapping("/{workspaceId}/registrations/{registrationId}") public RegistrationResponse registration(@PathVariable String workspaceId,@PathVariable String registrationId){return client.getRegistration(workspaceId,registrationId);}
}
