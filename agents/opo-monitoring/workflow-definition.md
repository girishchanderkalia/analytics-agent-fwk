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

  - id: read_distribution_stats
    type: capability
    capability: data_query.read_distribution_stats
    activity: Reading KPI distribution context

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

  - id: analyse_trends
    type: operation
    operation: analyse_trends
    activity: Identifying candidate outliers

  - id: approve_investigation
    type: approval
    approval: investigate_outlier
    decision_field: investigation_approved
    decision_fields:
      investigation_approved: approved
      selected_outlier: selected_outlier_id
    selection_from: outliers
    payload:
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

  - id: summarize_findings
    type: model
    prompt: findings_summary
    output: FindingsSummary
    output_to: findings
    inputs:
      - question
      - trend_filters
      - detection_scope
      - outliers
      - selected_outlier
      - workspace
      - registration
      - anomalous_wafers
    activity: Preparing evidence-based findings

edges:
  - from: parse_trend_request
    to: read_trends

  - from: read_trends
    to: read_distribution_stats

  - from: read_distribution_stats
    to: interpret_detection_scope

  - from: interpret_detection_scope
    to: analyse_trends

  - from: analyse_trends
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
    to: END

routing:
  defaults:
    analyse_trends: approve_investigation
    approve_investigation: create_workspace

  conditions:
    - from: analyse_trends
      when: "outliers == []"
      to: summarize_findings

    - from: approve_investigation
      when: "investigation_approved == false"
      to: END

approvals:
  - id: investigate_outlier
    required: true
    decision_field: investigation_approved
    title: Investigate selected outlier
    description: >
      Approve creation of an investigation workspace and access to
      wafer-level evidence.
---

# OPO Monitoring Investigation Workflow

The workflow contains four logical stages.

## 1. Interpret the request

The model extracts trend filters and the requested outlier criteria into typed
contracts.

## 2. Read and analyse trends

The runtime invokes the trend-query capability and then runs deterministic
application logic to identify candidate outliers.

The language model does not decide which trend rows satisfy the deterministic
outlier rule.

## 3. Request analyst approval

If candidate outliers exist, the runtime pauses and asks the analyst whether
the selected candidate should be investigated.

A rejected decision ends the investigation without creating a workspace.

## 4. Perform the deep investigation

After approval, the runtime:

1. Creates an investigation workspace.
2. Applies the selected filters.
3. Registers the required wafer-level data.
4. Reads wafer-level evidence.
5. Produces an evidence-based findings summary.

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