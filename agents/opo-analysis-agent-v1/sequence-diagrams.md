---
id: opo-analysis-agent-v1-sequences
version: "1.0"
kind: sequence-diagrams
---

# OPO Monitoring Interaction Sequences

## Existing deterministic application path

```mermaid
sequenceDiagram
    actor Analyst
    participant FE as OPO Monitoring FE
    participant Service as OPO Monitoring Service
    participant AF as Analytics Foundation APIs

    Analyst->>FE: Open trends or workspace function
    FE->>Service: Application request
    Service->>AF: Direct deterministic API request
    AF-->>Service: Platform response
    Service-->>FE: Application response
    FE-->>Analyst: Display result
```

The deterministic path does not use the Application Agent Runtime or the
Capability Adaptor.

## Analytics Copilot investigation path

```mermaid
sequenceDiagram
    actor Analyst
    participant CopilotFE as Analytics Copilot FE
    participant CopilotService as Analytics Copilot Service
    participant Runtime as Application Agent Runtime
    participant Agent as OPO Analysis Agent
    participant Model as Model Gateway
    participant Adaptor as Capability Adaptor
    participant AF as Analytics Foundation APIs

    Analyst->>CopilotFE: Ask an OPO investigation question
    CopilotFE->>CopilotService: Send conversation message
    CopilotService->>Runtime: Invoke agent conversation
    Runtime->>Agent: Load agent definitions

    Runtime->>Model: Parse trend filters
    Model-->>Runtime: Typed TrendFilters

    Runtime->>Adaptor: data_query.read_trends
    Adaptor->>AF: Query trend data
    AF-->>Adaptor: Trend rows
    Adaptor-->>Runtime: Normalized trend evidence

    opt Request did not ask for outliers
        Runtime-->>CopilotFE: Trend review approval
        Analyst->>CopilotFE: Continue to outlier detection
        CopilotFE->>Runtime: Resume conversation
    end

    Runtime->>Adaptor: data_query.read_distribution_stats
    Adaptor->>AF: Get filtered KPI distribution
    AF-->>Adaptor: Empirical statistics
    Adaptor-->>Runtime: Distribution evidence

    Runtime->>Model: Interpret outlier criteria with established filters and distribution evidence
    Model-->>Runtime: Typed DetectionScope

    opt No explicit threshold named
        Runtime-->>CopilotFE: Suggested threshold approval
        Analyst->>CopilotFE: Confirm threshold
        CopilotFE->>Runtime: Resume conversation
    end

    Runtime->>Agent: Run deterministic outlier analysis
    Agent-->>Runtime: Candidate outliers

    Runtime->>Adaptor: data_query.read_metadata
    Runtime->>Adaptor: data_query.preview_wafers
    Adaptor->>AF: Read-only wafer preview
    AF-->>Adaptor: Preview wafer rows
    Adaptor-->>Runtime: Wafer preview evidence

    Runtime-->>CopilotService: Approval request
    CopilotService-->>CopilotFE: Approval action
    CopilotFE-->>Analyst: Display approval request

    Analyst->>CopilotFE: Approve investigation
    CopilotFE->>CopilotService: Submit approval action
    CopilotService->>Runtime: Resume conversation

    Runtime->>Adaptor: data_query.investigate_outlier
    Adaptor->>AF: Read wafer evidence filtered to the selected outlier
    AF-->>Adaptor: Wafer rows
    Adaptor-->>Runtime: Normalized wafer evidence

    opt Anomalous wafers found
        Runtime-->>CopilotFE: Spatial analysis approval
        Analyst->>CopilotFE: Approve follow-up analysis
        CopilotFE->>Runtime: Resume conversation
        Runtime->>Agent: classify_spatial_pattern
        Agent-->>Runtime: Spatial pattern evidence
    end

    Runtime->>Model: Summarize supplied evidence
    Model-->>Runtime: Typed FindingsSummary

    Runtime-->>CopilotService: Findings and supported actions
    CopilotService-->>CopilotFE: Copilot response
    CopilotFE-->>Analyst: Display findings
```

## Rejected approval path

```mermaid
sequenceDiagram
    actor Analyst
    participant CopilotFE as Analytics Copilot FE
    participant CopilotService as Analytics Copilot Service
    participant Runtime as Application Agent Runtime

    Runtime-->>CopilotService: Investigation approval request
    CopilotService-->>CopilotFE: Approval action
    CopilotFE-->>Analyst: Display approval request

    Analyst->>CopilotFE: Reject investigation
    CopilotFE->>CopilotService: Submit rejection
    CopilotService->>Runtime: Resume with rejected decision

    Runtime-->>CopilotService: Investigation cancelled
    CopilotService-->>CopilotFE: Cancellation response
    CopilotFE-->>Analyst: Display cancellation
```

No workspace or data registration operation is executed after rejection.