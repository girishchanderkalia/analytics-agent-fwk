---
id: opo-monitoring-state
version: "1.0"
kind: state-model

fields:
  conversation_id:
    type: optional_string
    default: null
    description: Public conversation identifier.

  conversation_context:
    type: object
    default: {}
    description: Application context supplied to the agent.

  question:
    type: string
    default: ""
    description: Current analyst request.

  current_activity:
    type: optional_string
    default: null
    description: Current workflow activity shown by the Copilot experience.

  trend_filters:
    type: object
    default: {}
    description: Parsed trend filters.

  trend_series:
    type: object_list
    default: []
    description: Trend rows returned by the trend-query capability.

  detection_scope:
    type: object
    default: {}
    description: Selected outlier detection mode and threshold.

  threshold_context:
    type: object
    default: null
    description: Empirical KPI distribution context used for threshold interpretation.

  analysis:
    type: object_list
    default: []
    description: Deterministic trend-analysis results.

  outliers:
    type: object_list
    default: []
    description: Candidate outliers identified by trend analysis.

  selected_outlier:
    type: object
    default: null
    description: Candidate selected by the analyst for investigation.

  pending_action:
    type: object
    default: null
    description: Approval or clarification action waiting for a user response.

  investigation_approved:
    type: boolean
    default: false
    description: Whether the analyst approved the investigation.

  workspace:
    type: object
    default: null
    description: Workspace evidence returned by Analytics Foundation.

  applied_filters:
    type: object
    default: {}
    description: Filters applied to the investigation workspace.

  registration:
    type: object
    default: null
    description: Dataset registration evidence.

  registration_poll_count:
    type: integer
    default: 0
    description: >
      Number of registration-status checks performed during the current
      workflow execution.

  anomalous_wafers:
    type: object_list
    default: []
    description: Wafer records identified as anomalous.

  wafer_rows:
    type: object_list
    default: []
    description: Wafer-level evidence returned by the query capability.

  findings:
    type: object
    default: null
    description: Structured evidence-based findings.

  artifacts:
    type: object_list
    default: []
    description: Artifacts exposed to the Copilot frontend.

  cancelled_at:
    type: optional_string
    default: null
    description: Workflow point at which the analyst cancelled execution.

  error:
    type: optional_string
    default: null
    description: Current execution error when workflow processing fails.
---

# OPO Monitoring State Model

The state model contains application context, parsed intent, trend evidence,
outlier analysis, human decisions, Analytics Foundation operation results, and
structured findings.

## State rules

- Secrets and credentials must not be stored in workflow state.
- Access tokens must not be stored in workflow state.
- Raw request headers must not be stored in workflow state.
- Every finding must reference evidence available in workflow state.
- Human approval must be recorded before protected capabilities run.
- Capability results must be mapped into explicitly declared state fields.
- Runtime implementation details must not be exposed as business evidence.
- Conversation identifiers must be separated from LangGraph checkpoint IDs.

## State lifecycle

```mermaid
stateDiagram-v2
    [*] --> RequestReceived
    RequestReceived --> FiltersParsed
    FiltersParsed --> TrendsLoaded
    TrendsLoaded --> DetectionScopeInterpreted
    DetectionScopeInterpreted --> OutliersAnalysed

    OutliersAnalysed --> Findings: no candidate outliers
    OutliersAnalysed --> InvestigationApproval: candidate found

    InvestigationApproval --> Cancelled: rejected
    InvestigationApproval --> WorkspaceCreated: approved

    WorkspaceCreated --> FiltersApplied
    FiltersApplied --> DataRegistered
    DataRegistered --> WaferEvidenceLoaded
    WaferEvidenceLoaded --> Findings

    Findings --> [*]
    Cancelled --> [*]
```

## Evidence state

The following state fields may be cited as evidence:

- `trend_filters`
- `trend_series`
- `detection_scope`
- `analysis`
- `outliers`
- `selected_outlier`
- `workspace`
- `applied_filters`
- `registration`
- `anomalous_wafers`
- `wafer_rows`

The `findings` field is an output derived from evidence. The `findings` field is
not independent source evidence.