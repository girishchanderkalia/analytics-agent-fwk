---
id: opo-monitoring-workflow
version: "1.0"
kind: workflow

entry_node: parse_trend_request

nodes:
  - id: parse_trend_request
    type: model
    prompt: trend_filters
    output: TrendFilters
    output_to: trend_filters
    activity: Interpreting the investigation request

  - id: read_trends
    type: capability
    capability: data_query.read_trends
    activity: Reading OPO KPI trends

  - id: review_trends
    type: approval
    approval: continue_to_outlier_detection
    decision_field: outlier_detection_requested
    decision_fields:
      outlier_detection_requested: approved
    payload:
      question: Trend chart ready. Continue to outlier detection?
      approve_label: Detect outliers
      reject_label: Stop here
      details:
        Filters: ${state.trend_filters.interpretation}
      trend_filters: ${state.trend_filters}
    activity: Waiting for the analyst to review the trend chart

  - id: interpret_detection_scope
    type: model
    prompt: detection_scope
    output: DetectionScope
    output_to: detection_scope
    tools:
      - data_query.read_distribution_stats
    max_tool_calls: 1
    grounded_outputs:
      suggested_limit_value:
        - p95
        - p99
    inputs:
      - question
      - trend_filters
    activity: Interpreting the outlier criteria

  - id: confirm_threshold
    type: approval
    approval: confirm_suggested_threshold
    decision_field: threshold_confirmed
    decision_fields:
      threshold_confirmed: approved
      confirmed_threshold: limit_value
    payload:
      question: Apply the suggested absolute OPO KPI threshold, or enter your own?
      approve_label: Apply threshold
      reject_label: Cancel
      details:
        Suggested threshold: ${state.detection_scope.suggested_limit_value}
        Direction: ${state.detection_scope.direction}
        Rationale: ${state.detection_scope.suggested_limit_rationale}
      input:
        name: limit_value
        label: Absolute OPO KPI threshold
        type: number
        value: ${state.detection_scope.suggested_limit_value}
      detection_scope: ${state.detection_scope}
    activity: Waiting for threshold confirmation

  - id: analyse_trends_with_confirmed_threshold
    type: operation
    operation: analyse_trends_with_confirmed_threshold
    activity: Identifying candidate outliers

  - id: analyse_trends
    type: operation
    operation: analyse_trends
    activity: Identifying candidate outliers

  - id: read_metadata
    type: capability
    capability: data_query.read_metadata
    activity: Resolving the wafer dataset

  - id: preview_wafers
    type: capability
    capability: data_query.preview_wafers
    activity: Previewing wafer-level data

  - id: approve_investigation
    type: approval
    approval: investigate_outlier
    decision_field: investigation_approved
    decision_fields:
      investigation_approved: approved
      selected_outlier: selected_outlier_id
    selection_from: outliers
    payload:
      question: Investigate the selected outlier?
      approve_label: Investigate
      reject_label: Reject
      detected_outliers: ${state.outliers}
      selected_outlier: ${state.selected_outlier}
    activity: Waiting for investigation approval

  - id: create_workspace
    type: capability
    capability: workspace.create
    activity: Creating an investigation workspace

  - id: apply_filters
    type: capability
    capability: workspace.add_filters
    activity: Applying investigation filters

  - id: register_data
    type: capability
    capability: workspace.register_dataset
    activity: Registering wafer-level data

  - id: read_wafers
    type: capability
    capability: data_query.read_wafers
    activity: Reading wafer-level evidence

  - id: classify_spatial_pattern
    type: operation
    operation: classify_spatial_pattern
    activity: Classifying the anomalous wafer spatial pattern

  - id: summarize_findings
    type: model
    prompt: findings_summary
    output: FindingsSummary
    output_to: findings
    inputs:
      - question
      - trend_filters
      - detection_scope
      - confirmed_threshold
      - outliers
      - selected_outlier
      - workspace
      - registration
      - anomalous_wafers
      - spatial_pattern
    activity: Preparing evidence-based findings

  - id: select_next_action
    type: approval
    approval: select_recommended_action
    decision_field: next_action_approved
    decision_fields:
      next_action_approved: approved
      selected_action: selected_action
    payload:
      question: Which recommended follow-up action should I perform?
      approve_label: Approve action
      reject_label: Skip
      options: ${state.findings.recommended_next_actions}
    activity: Waiting for the analyst to select and approve a recommended action

edges:
  - from: parse_trend_request
    to: read_trends

  - from: read_trends
    to: review_trends

  - from: review_trends
    to: interpret_detection_scope

  - from: interpret_detection_scope
    to: analyse_trends

  - from: confirm_threshold
    to: analyse_trends_with_confirmed_threshold

  - from: analyse_trends
    to: read_metadata

  - from: analyse_trends_with_confirmed_threshold
    to: read_metadata

  - from: read_metadata
    to: preview_wafers

  - from: preview_wafers
    to: approve_investigation

  - from: approve_investigation
    to: create_workspace

  - from: create_workspace
    to: apply_filters

  - from: apply_filters
    to: register_data

  - from: register_data
    to: read_wafers

  - from: read_wafers
    to: summarize_findings

  - from: summarize_findings
    to: select_next_action

  - from: select_next_action
    to: classify_spatial_pattern

  - from: classify_spatial_pattern
    to: END

routing:
  defaults:
    read_trends: review_trends
    review_trends: interpret_detection_scope
    interpret_detection_scope: analyse_trends
    confirm_threshold: analyse_trends_with_confirmed_threshold
    analyse_trends: read_metadata
    analyse_trends_with_confirmed_threshold: read_metadata
    approve_investigation: create_workspace
    read_wafers: summarize_findings
    summarize_findings: select_next_action
    select_next_action: END

  conditions:
    # A first message that already asks for outliers skips the trend review pause.
    - from: read_trends
      when: "trend_filters.outliers_requested == true"
      to: interpret_detection_scope

    - from: review_trends
      when: "outlier_detection_requested == false"
      to: END

    - from: interpret_detection_scope
      when: "detection_scope.suggested_limit_value != null"
      to: confirm_threshold

    - from: confirm_threshold
      when: "threshold_confirmed == false"
      to: END

    - from: analyse_trends
      when: "outliers == []"
      to: summarize_findings

    - from: analyse_trends_with_confirmed_threshold
      when: "outliers == []"
      to: summarize_findings

    - from: approve_investigation
      when: "investigation_approved == false"
      to: END

    - from: read_wafers
      when: "anomalous_wafers == []"
      to: summarize_findings

    - from: select_next_action
      when: "next_action_approved == false"
      to: END

    - from: select_next_action
      when: 'selected_action == "Analyze wafer spatial pattern"'
      to: classify_spatial_pattern

approvals:
  - id: continue_to_outlier_detection
    required: true
    decision_field: outlier_detection_requested
    title: Continue to outlier detection
    description: >
      The trend chart is ready. Approve to detect outliers within the
      displayed filters.

  - id: confirm_suggested_threshold
    required: true
    decision_field: threshold_confirmed
    title: Confirm suggested threshold
    description: >
      No explicit threshold was given. Approve the absolute OPO KPI cutoff
      recommended from the empirical distribution statistics.

  - id: select_recommended_action
    required: true
    decision_field: next_action_approved
    title: Select and approve a recommended action
    description: >
      The analyst selects one of the model's recommended actions and approves
      it before the workflow proceeds. Only supported actions are executed.

  - id: investigate_outlier
    required: true
    decision_field: investigation_approved
    title: Investigate selected outlier
    description: >
      Approve creation of an investigation workspace and access to
      wafer-level evidence.
---

# OPO Monitoring Investigation Workflow

The workflow contains five analyst-facing steps. Each rejection ends the
investigation before any later side effect runs.

## 1. Display trends

The model extracts trend filters and the runtime reads the trend series. When
the request did not already ask for outliers, the runtime pauses so the analyst
can review the trend chart before continuing to outlier detection.

## 2. Interpret and confirm the outlier threshold

The model interprets the outlier criteria within the established filters. When
no explicit threshold was named, it recommends a cutoff grounded in the
distribution statistics and the runtime pauses for the analyst to confirm it.

## 3. Select an outlier to investigate

Deterministic application logic identifies candidate outliers. The language
model does not decide which trend rows satisfy the outlier rule. A read-only
wafer preview is loaded, then the runtime pauses for the analyst to approve the
investigation of a selected candidate.

## 4. Perform the deep investigation

After approval, the runtime:

1. Creates an investigation workspace.
2. Applies the selected filters.
3. Registers the required wafer-level data.
4. Reads wafer-level evidence.

## 5. Findings and recommended actions

The findings summary is produced first. The analyst can then select one of the
model's recommended actions from a dropdown and approve it. The existing
"Analyze wafer spatial pattern" action runs the deterministic classifier;
recommendations without an implemented capability are not executed.

## Observability

Every operation is represented explicitly so the runtime can expose:

- current activity
- model activity
- capability activity
- approval requests
- capability results
- errors
- completion status

## Runtime compatibility note

The v3 execution engine must recognize these node types:

- `model`
- `operation`
- `capability`
- `approval`

The `operation` node type represents deterministic application logic that does
not call the model and does not call Analytics Foundation.