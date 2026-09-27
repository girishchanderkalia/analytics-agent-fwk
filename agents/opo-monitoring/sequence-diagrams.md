---
id: opo-monitoring-sequences
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
    participant Agent as OPO Monitoring Agent
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

    Runtime->>Model: Interpret outlier criteria with established filters
    Model->>Runtime: Call get_distribution_stats (at most once)
    Runtime->>Adaptor: data_query.read_distribution_stats
    Adaptor->>AF: Get filtered KPI distribution
    AF-->>Adaptor: Empirical statistics
    Adaptor-->>Runtime: Distribution evidence
    Runtime-->>Model: Tool result
    Model-->>Runtime: Typed DetectionScope

    Runtime->>Agent: Run deterministic outlier analysis
    Agent-->>Runtime: Candidate outliers

    Runtime-->>CopilotService: Approval request
    CopilotService-->>CopilotFE: Approval action
    CopilotFE-->>Analyst: Display approval request

    Analyst->>CopilotFE: Approve investigation
    CopilotFE->>CopilotService: Submit approval action
    CopilotService->>Runtime: Resume conversation

    Runtime->>Adaptor: workspace.create
    Adaptor->>AF: Create workspace
    AF-->>Adaptor: Workspace evidence
    Adaptor-->>Runtime: Normalized workspace evidence

    Runtime->>Adaptor: workspace.add_filters
    Adaptor->>AF: Apply filters
    AF-->>Adaptor: Applied filter evidence
    Adaptor-->>Runtime: Normalized filter evidence

    Runtime->>Adaptor: workspace.register_dataset
    Adaptor->>AF: Register wafer data
    AF-->>Adaptor: Registration evidence
    Adaptor-->>Runtime: Normalized registration evidence

    Runtime->>Adaptor: data_query.read_wafers
    Adaptor->>AF: Read wafer evidence
    AF-->>Adaptor: Wafer rows
    Adaptor-->>Runtime: Normalized wafer evidence

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