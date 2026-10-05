---
id: opo-analysis-agent-v4-state
version: "4.0"
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

  change_suggestion:
    type: object
    default: {}
    description: Suggested change date and prefilled follow-up question from the daily X/Y means.

  comparison_requested:
    type: boolean
    default: false
    description: Whether the analyst requested a before/after comparison.

  comparison_request:
    type: string
    default: ""
    description: Analyst's follow-up question describing the observed jump.

  comparison_scope:
    type: object
    default: null
    description: Parsed before/after change date.

  tdbb_run:
    type: object
    default: null
    description: TDBB run result with run IDs, budgets and wafer/field maps per period.

  tdbb_runs:
    type: object_list
    default: []
    description: Before and after TDBB results returned by Foundation MCP.

  tdbb_model_analysis:
    type: object
    default: null
    description: Model interpretation grounded in the Foundation TDBB compare response.

  tdbb_before_analysis:
    type: object
    default: null
    description: Intermediate model output from the before-period evidence request.

  tdbb_after_analysis:
    type: object
    default: null
    description: Intermediate model output from the after-period evidence request.

  tdbb_before_run:
    type: object
    default: null
    description: Foundation TDBB result for the before period.

  tdbb_after_run:
    type: object
    default: null
    description: Foundation TDBB result for the after period.

  tdbb_comparison:
    type: object
    default: null
    description: Before/after TDBB budget deltas and the largest increase.

  tdbb_explanation_requested:
    type: boolean
    default: false
    description: Whether the analyst asked for an explanation after reviewing the TDBB overview.

  tdbb_summary:
    type: object
    default: null
    description: Analyst-facing summary of the TDBB comparison.

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

  selected_action:
    type: optional_string
    default: null
    description: Recommended action selected by the analyst.

  next_action_approved:
    type: boolean
    default: false
    description: Whether the analyst approved the selected recommended action.

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

  outlier_detection_requested:
    type: boolean
    default: false
    description: Whether the analyst continued from the trend chart to outlier detection.

  threshold_confirmed:
    type: boolean
    default: false
    description: Whether the analyst accepted the suggested absolute OPO KPI threshold.

  confirmed_threshold:
    type: optional_float
    default: null
    description: >
      Absolute OPO KPI threshold the analyst confirmed or entered in place of
      the suggested value.

  dataset_metadata:
    type: object
    default: null
    description: Dataset and table names published by Analytics Foundation.

  spatial_pattern:
    type: object
    default: null
    description: Edge-versus-center classification of anomalous wafer points.
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
    TrendsLoaded --> TrendReview: trend display request
    TrendsLoaded --> DetectionScopeInterpreted: outliers requested
    TrendReview --> Cancelled: rejected
    TrendReview --> DetectionScopeInterpreted: approved

    DetectionScopeInterpreted --> ThresholdConfirmation: suggested threshold
    DetectionScopeInterpreted --> OutliersAnalysed: explicit threshold
    ThresholdConfirmation --> Cancelled: rejected
    ThresholdConfirmation --> OutliersAnalysed: approved

    OutliersAnalysed --> Findings: no candidate outliers
    OutliersAnalysed --> WaferPreviewLoaded: candidate found
    WaferPreviewLoaded --> InvestigationApproval

    InvestigationApproval --> Cancelled: rejected
    InvestigationApproval --> WorkspaceCreated: approved

    WorkspaceCreated --> FiltersApplied
    FiltersApplied --> DataRegistered
    DataRegistered --> WaferEvidenceLoaded
    WaferEvidenceLoaded --> Findings
    Findings --> RecommendedActionSelection
    RecommendedActionSelection --> SpatialPatternClassified: approved supported action
    RecommendedActionSelection --> [*]: skipped or unsupported action
    SpatialPatternClassified --> [*]
    Cancelled --> [*]
```

## Evidence state

The following state fields may be cited as evidence:

- `trend_filters`
- `trend_series`
- `comparison_scope`
- `tdbb_run`
- `tdbb_comparison`
- `detection_scope`
- `analysis`
- `outliers`
- `selected_outlier`
- `workspace`
- `applied_filters`
- `registration`
- `anomalous_wafers`
- `wafer_rows`
- `spatial_pattern`

The `findings` field is an output derived from evidence. The `findings` field is
not independent source evidence.