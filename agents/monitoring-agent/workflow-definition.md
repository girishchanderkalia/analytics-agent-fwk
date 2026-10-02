---
id: monitoring-agent-workflow
version: "1.0"
kind: workflow

entry_node: parse_trend_request

nodes:
  - id: parse_trend_request
    type: model
    prompt: trend_filters
    output: TrendFilters
    output_to: trend_filters
    cacheable: true
    activity: Interpreting the investigation request

  - id: request_trend_evidence
    type: capability
    capability: data_query.read_trends
    output_to: trend_series
    inputs:
      - trend_filters
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

  - id: read_distribution_stats
    type: capability
    capability: data_query.read_distribution_stats
    output_to: threshold_context
    inputs:
      - trend_filters
    activity: Reading the empirical KPI distribution

  - id: interpret_detection_scope
    type: model
    prompt: detection_scope
    output: DetectionScope
    output_to: detection_scope
    inputs:
      - question
      - trend_filters
      - threshold_context
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
    type: capability
    capability: data_query.detect_outliers_with_confirmed_threshold
    output_to: outliers
    inputs:
      - trend_filters
      - confirmed_threshold
    activity: Identifying candidate outliers

  - id: analyse_trends
    type: capability
    capability: data_query.detect_outliers
    output_to: outliers
    inputs:
      - trend_filters
      - detection_scope
    activity: Identifying candidate outliers

  - id: read_metadata
    type: capability
    capability: data_query.read_metadata
    output_to: dataset_metadata
    inputs:
      - trend_filters
    activity: Resolving the wafer dataset

  - id: preview_wafers
    type: capability
    capability: data_query.preview_wafers
    output_to: wafer_rows
    inputs:
      - dataset_metadata
      - outliers
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

  - id: investigate_selected_outlier
    type: capability
    capability: data_query.investigate_outlier
    output_to: wafer_rows
    inputs:
      - dataset_metadata
      - selected_outlier
    activity: Reading wafer-level evidence for the selected outlier

  - id: classify_spatial_pattern
    type: model
    prompt: spatial_pattern
    output: SpatialPattern
    output_to: spatial_pattern
    input_projection:
      anomalous_wafers: $.anomalous_wafers
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
    to: request_trend_evidence

  - from: request_trend_evidence
    to: review_trends

  - from: review_trends
    to: read_distribution_stats

  - from: read_distribution_stats
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
    to: investigate_selected_outlier

  - from: investigate_selected_outlier
    to: summarize_findings

  - from: summarize_findings
    to: select_next_action

  - from: select_next_action
    to: classify_spatial_pattern

  - from: classify_spatial_pattern
    to: END

routing:
  defaults:
    request_trend_evidence: review_trends
    review_trends: read_distribution_stats
    read_distribution_stats: interpret_detection_scope
    interpret_detection_scope: analyse_trends
    confirm_threshold: analyse_trends_with_confirmed_threshold
    analyse_trends: read_metadata
    analyse_trends_with_confirmed_threshold: read_metadata
    approve_investigation: investigate_selected_outlier
    investigate_selected_outlier: summarize_findings
    summarize_findings: select_next_action
    select_next_action: END

  conditions:
    # A first message that already asks for outliers skips the trend review pause.
    - from: request_trend_evidence
      when: "trend_filters.outliers_requested == true"
      to: read_distribution_stats

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
      Approve reading wafer-level evidence scoped to the selected candidate
      outlier.
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

After approval, deterministic application logic reads wafer-level evidence
scoped to the selected candidate's machine, layer, and lot. The language model
does not decide which wafer rows are read.

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