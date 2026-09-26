package com.asml.analytics.facade.client;

import com.asml.analytics.facade.dto.foundation.*;

public interface AnalyticsFoundationClient {
    TrendResponse queryTrends(TrendQuery request);
    DistributionResponse getDistribution(DistributionQuery request);
    WorkspaceResponse createWorkspace(CreateWorkspaceRequest request);
    WorkspaceFiltersResponse applyFilters(String workspaceId, ApplyFiltersRequest request);
    ConnectionInfoResponse getConnectionInfo(String workspaceId);
    RegistrationResponse registerDataset(String workspaceId, RegistrationRequest request);
    RegistrationResponse getRegistration(String workspaceId, String registrationId);
    WaferQueryResponse queryWafers(WaferQueryRequest request);
}
