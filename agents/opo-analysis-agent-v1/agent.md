---
id: opo-analysis-agent-v1
version: "V1"
kind: agent
display_name: OPO Analysis Agent
description: >
  Supports conversational investigation of OPO KPI trends, candidate
  outliers, and wafer-level evidence using governed Analytics Foundation capabilities.
ownership:
  owner: OPO Monitoring application
  runtime_owner: Application Agent Runtime
defaults:
  outlier_mode: baseline
  limit_value: 3.0
  baseline_deviation_pct: 3.0
conversation:
  welcome_message: >
    I can help investigate OPO trends, identify candidate outliers, and
    perform an analyst-approved wafer-level investigation.
  suggested_prompts:
    - Show OPO trends for the last seven days.
    - Identify significant outliers.
    - Investigate the selected outlier.
    - Explain the evidence behind the finding.
context:
  accepted:
    - application_id
    - route
    - selected_lot_ids
    - selected_product_ids
    - selected_layer_ids
    - selected_equipment_ids
    - workspace_id

knowledge:
  always: |
    Use only supplied application context and evidence. Do not invent identifiers,
    KPI definitions, measurements, datasets, time ranges or process relationships.
    Runtime information is operational context and must not be presented as domain evidence.
    A finding may describe supplied trends, threshold violations, comparisons,
    grouping or spatial patterns, and limitations of the available evidence.
    A plausible explanation remains an alternative explanation until additional
    evidence confirms it. A threshold violation or observed pattern is not a confirmed cause.
    Low confidence means limited evidence or multiple explanations. Medium confidence
    means a consistent pattern without established causality. High confidence requires
    directly and consistently supporting evidence, and does not establish a root cause.
    Model findings are derived interpretations, not independent source evidence.
    Use governed Foundation tools; never access Foundation backing stores directly.
  topics:
    trends: |
      A trend is a time-ordered representation of the application-defined OPO KPI.
      V1 scope comes only from the analyst's request, not inferred application inventory.
      The agent's default scope is all available dates, products, layers, lots and scanners.
      Empty identifier lists and null date fields represent that unrestricted scope.
      Missing filter values are empty or null; do not guess a lookback window.
      available_trend_scopes describes available data, not the analyst's selection.
      Do not turn that advertised product, layer or scanner inventory into filters.
      Foundation query results, not model-generated values, are the trend evidence.
    outliers: |
      Detection scope is the deterministic rule and threshold used to identify candidates.
      An outlier is an observation violating that selected rule, not a confirmed root cause.
      A number with % is a percentage threshold; a unitless number is an absolute KPI threshold.
      Use supplied distribution statistics to recommend a cutoff, not model estimates.
      Zero samples mean missing distribution evidence. Never invent a cutoff in that case.
      The analyst-selected outlier is a candidate for investigation, not independent evidence.
    wafers: |
      Wafer-level rows and anomalous wafer points come from governed Foundation queries.
      Trend observations are lot-level aggregates; lot_id joins the selected observation
      to wafer data, which is available for only a subset of lots.
      Spatial classification may describe a pattern only when supplied points support it.
      It must not infer a process cause. Missing wafer evidence is a limitation, not a normal pattern.
      "Analyze wafer spatial pattern" is the only supported follow-up action; it requires approval.

state:
  conversation_id: {type: optional_string, default: null, description: Public conversation identifier.}
  conversation_context: {type: object, default: {}, description: Application context supplied to the agent.}
  question: {type: string, default: "", description: Current analyst request.}
  current_activity: {type: optional_string, default: null, description: Current workflow activity shown by the Copilot experience.}
  trend_filters: {type: object, default: {}, description: Parsed trend filters.}
  trend_series: {type: object_list, default: [], description: Trend rows returned by the model-mediated Foundation query.}
  trend_evidence: {type: object, default: null, description: Model response grounded in Foundation trend evidence.}
  metadata_evidence: {type: object, default: null, description: Model response grounded in Foundation metadata.}
  preview_evidence: {type: object, default: null, description: Model response grounded in Foundation wafer preview evidence.}
  wafer_evidence: {type: object, default: null, description: Model response grounded in Foundation wafer evidence.}
  workspace_request: {type: object, default: null, description: Model request record for the Foundation workspace operation.}
  filter_request: {type: object, default: null, description: Model request record for applying Foundation workspace filters.}
  registration_request: {type: object, default: null, description: Model request record for registering the Foundation dataset.}
  detection_scope: {type: object, default: {}, description: Selected outlier detection mode and threshold.}
  threshold_context: {type: object, default: null, description: Empirical KPI distribution context used for threshold interpretation.}
  analysis: {type: object_list, default: [], description: Deterministic trend-analysis results.}
  outliers: {type: object_list, default: [], description: Candidate outliers identified by trend analysis.}
  selected_outlier: {type: object, default: null, description: Candidate selected by the analyst for investigation.}
  pending_action: {type: object, default: null, description: Approval or clarification action waiting for a user response.}
  investigation_approved: {type: boolean, default: false, description: Whether the analyst approved the investigation.}
  anomalous_wafers: {type: object_list, default: [], description: Wafer records identified as anomalous.}
  wafer_rows: {type: object_list, default: [], description: Wafer-level evidence returned by the query capability.}
  findings: {type: object, default: null, description: Structured evidence-based findings.}
  selected_action: {type: optional_string, default: null, description: Recommended action selected by the analyst.}
  next_action_approved: {type: boolean, default: false, description: Whether the analyst approved the selected recommended action.}
  artifacts: {type: object_list, default: [], description: Artifacts exposed to the Copilot frontend.}
  cancelled_at: {type: optional_string, default: null, description: Workflow point at which the analyst cancelled execution.}
  error: {type: optional_string, default: null, description: Current execution error when workflow processing fails.}
  outlier_detection_requested: {type: boolean, default: false, description: Whether the analyst continued from the trend chart to outlier detection.}
  threshold_confirmed: {type: boolean, default: false, description: Whether the analyst accepted the suggested absolute OPO KPI threshold.}
  confirmed_threshold:
    type: optional_float
    default: null
    description: >
      Absolute OPO KPI threshold the analyst confirmed or entered in place of
      the suggested value.
  dataset_metadata: {type: object, default: null, description: Dataset and table names published by Analytics Foundation.}
  spatial_pattern: {type: object, default: null, description: Edge-versus-center classification of anomalous wafer points.}
  filter_validation: {type: object, default: null, description: Filter-provenance validation report; operational metadata rather than measurement evidence.}

steps:
  - id: parse_trend_request
    type: model
    output_to: trend_filters
    cacheable: true
    input_projection:
      question: $.question
      current_date: $.conversation_context.current_date
    knowledge: [trends]
    activity: Interpreting the investigation request
    instructions: |
      Extract trend filters from the analyst request.

      Do not invent lot identifiers, product identifiers, layer identifiers,
      equipment identifiers, dates, or filter values.

      Use only the analyst's question to select scope. current_date is supplied
      solely to interpret explicitly requested relative dates or omitted years.

      When a value is not present, leave the corresponding field empty or null.

      available_trend_scopes is discovery metadata, not selected filters. Never
      populate product_ids, layer_ids or exposure_equipment_ids from its inventory.
      Only use identifiers explicitly requested by the analyst. V1 does not apply
      application selections or inventory as implicit scope.
      For a bare "show outliers", leave every
      identifier list empty and lookback_days, start_date and end_date null so that
      Foundation queries all available dates and scopes.

      Set outliers_requested to true only when the request asks for outliers,
      anomalies, extreme values, or names a threshold; otherwise set it to false
      so the analyst can review the trend chart first.
    guardrails:
      report_to: filter_validation
      retries: 1
      on_failure: stop
      rules:
        - {field: lot_ids, rule: mentioned_in, source: $.question}
        - {field: product_ids, rule: mentioned_in, source: $.question}
        - {field: layer_ids, rule: mentioned_in, source: $.question}
        - {field: exposure_equipment_ids, rule: mentioned_in, source: $.question}
    output:
      lookback_days:
        type: optional_int
        default: null
        description: >
          Relative lookback period in days. Leave null unless the analyst names
          a period; a guessed window hides older evidence.
      start_date: {type: optional_string, default: null, description: Inclusive ISO start date.}
      end_date: {type: optional_string, default: null, description: Inclusive ISO end date.}
      lot_ids: {type: string_list, default: [], description: Lot identifiers selected for trend analysis.}
      product_ids: {type: string_list, default: [], description: Product identifiers selected for trend analysis.}
      layer_ids: {type: string_list, default: [], description: Layer identifiers selected for trend analysis.}
      exposure_equipment_ids: {type: string_list, default: [], description: Exposure equipment identifiers.}
      interpretation: {type: string, default: "", description: Short interpretation of the requested filters.}
      outliers_requested:
        type: boolean
        default: false
        description: >
          True when the request already asks for outliers, anomalies,
          extreme values, or a threshold; false for a trend display request.

  - id: request_trend_evidence
    type: capability
    output_to: trend_series
    inputs: [trend_filters]
    activity: Reading OPO KPI trends
    capability:
      operation: query_trends
      server: analytics-foundation
      tool: query_trend_series
      owner: Analytics Foundation
      version: "1"
      permissions: [query:trends:read]
      side_effect: false
      approval_required: false
      request: &trend_request
        days: ${state.trend_filters.lookback_days}
        start_date: ${state.trend_filters.start_date}
        end_date: ${state.trend_filters.end_date}
        lot_ids: ${state.trend_filters.lot_ids}
        product_ids: ${state.trend_filters.product_ids}
        layer_ids: ${state.trend_filters.layer_ids}
        exposure_equipment_ids: ${state.trend_filters.exposure_equipment_ids}
      result:
        trend_series: ${result.series}

  - id: review_trends
    type: approval
    decision_field: outlier_detection_requested
    activity: Waiting for the analyst to review the trend chart
    approval:
      id: continue_to_outlier_detection
      required: true
      decision_field: outlier_detection_requested
      title: Continue to outlier detection
      description: >
        The trend chart is ready. Approve to detect outliers within the
        displayed filters.
    payload:
      question: Trend chart ready. Continue to outlier detection?
      approve_label: Detect outliers
      reject_label: Stop here
      details:
        Filters: ${state.trend_filters.interpretation}
      trend_filters: ${state.trend_filters}
    responses:
      outlier_detection_requested: {from: approved, type: boolean, default: false}

  - id: read_distribution_stats
    type: capability
    output_to: threshold_context
    inputs: [trend_filters]
    activity: Reading the empirical KPI distribution
    capability:
      operation: read_distribution_stats
      server: analytics-foundation
      tool: get_distribution_stats
      owner: Analytics Foundation
      version: "1"
      permissions: [query:trends:read]
      side_effect: false
      approval_required: false
      request: *trend_request
      result:
        threshold_context: ${result}

  - id: interpret_detection_scope
    type: model
    output_to: detection_scope
    inputs: [question, trend_filters, threshold_context]
    knowledge: [outliers]
    activity: Interpreting the outlier criteria
    instructions: |
      Interpret the analyst's outlier request within the established trend filters.
      Do not re-extract or change those filters. A number with % is a percentage
      threshold; a unitless number is an absolute OPO KPI threshold. An explicit
      numeric threshold takes precedence: leave suggested_limit_value and
      suggested_limit_rationale null when one was given.

      Reaching this step always means outlier detection was requested, even when
      the analyst's wording does not say "outlier". For a request without an
      explicit numeric threshold, recommend an absolute OPO KPI cutoff grounded
      in the supplied threshold_context (p95, p99, mean, stdev, bell_curve_range);
      never invent or estimate distribution statistics. Recommend p95 by default
      and p99 only for severe anomaly detection. Set suggested_limit_value and
      suggested_limit_rationale from that evidence, and set mode to absolute,
      limit_value to the suggested value, direction to above, and threshold_unit
      to absolute. Never leave limit_value empty when recommending a cutoff. Use
      baseline (per-machine) mode only when the analyst explicitly asks to
      compare each machine against its own history or baseline.

      If threshold_context.sample_count is zero, leave suggested_limit_value null
      and explain the missing data in suggested_limit_rationale; do not guess a
      cutoff. Do not claim that a threshold violation establishes a root cause.
    output:
      mode: {type: literal, values: [absolute, baseline], default: baseline, description: Outlier detection mode.}
      limit_value: {type: float, default: 3.0, description: Absolute KPI threshold used in absolute mode.}
      direction: {type: literal, values: [below, above], default: below, description: Direction used to identify threshold violations.}
      threshold_unit: {type: literal, values: [percent, absolute], default: percent, description: Unit used for the threshold.}
      baseline_deviation_pct: {type: optional_float, default: null, description: Allowed percentage deviation from the baseline.}
      interpretation: {type: string, default: "", description: Short interpretation of the outlier request.}
      suggested_limit_value: {type: optional_float, default: null, description: Recommended absolute cutoff when clarification is needed.}
      suggested_limit_rationale: {type: optional_string, default: null, description: Evidence-based explanation of the suggested cutoff.}

  - id: confirm_threshold
    type: approval
    decision_field: threshold_confirmed
    activity: Waiting for threshold confirmation
    approval:
      id: confirm_suggested_threshold
      required: true
      decision_field: threshold_confirmed
      title: Confirm suggested threshold
      description: >
        No explicit threshold was given. Approve the absolute OPO KPI cutoff
        recommended from the empirical distribution statistics.
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
    responses:
      threshold_confirmed: {from: approved, type: boolean, default: false}
      confirmed_threshold: {from: limit_value, type: optional_float, default: null}

  - id: analyse_trends_with_confirmed_threshold
    type: capability
    output_to: outliers
    inputs: [trend_filters, confirmed_threshold]
    activity: Identifying candidate outliers
    capability:
      operation: detect_outliers
      server: analytics-foundation
      tool: detect_outliers
      owner: Analytics Foundation
      version: "1"
      permissions: [query:trends:read]
      side_effect: false
      approval_required: false
      request:
        <<: *trend_request
        mode: absolute
        limit_value: ${state.confirmed_threshold}
        direction: above
        threshold_unit: absolute
      result:
        outliers: ${result.outliers}

  - id: analyse_trends
    type: capability
    output_to: outliers
    inputs: [trend_filters, detection_scope]
    activity: Identifying candidate outliers
    capability:
      operation: detect_outliers
      server: analytics-foundation
      tool: detect_outliers
      owner: Analytics Foundation
      version: "1"
      permissions: [query:trends:read]
      side_effect: false
      approval_required: false
      request:
        <<: *trend_request
        mode: ${state.detection_scope.mode}
        limit_value: ${state.detection_scope.limit_value}
        direction: ${state.detection_scope.direction}
        threshold_unit: ${state.detection_scope.threshold_unit}
        baseline_deviation_pct: ${state.detection_scope.baseline_deviation_pct}
      result:
        outliers: ${result.outliers}

  - id: read_metadata
    type: capability
    output_to: dataset_metadata
    inputs: [trend_filters]
    activity: Resolving the wafer dataset
    capability:
      operation: read_metadata
      server: analytics-foundation
      tool: get_metadata
      owner: Analytics Foundation
      version: "1"
      permissions: [query:metadata:read]
      side_effect: false
      approval_required: false
      request: {}
      result:
        dataset_metadata: ${result}

  - id: preview_wafers
    type: capability
    output_to: wafer_rows
    inputs: [dataset_metadata, outliers]
    activity: Previewing wafer-level data
    capability:
      operation: preview_wafers
      server: analytics-foundation
      tool: query_wafers
      owner: Analytics Foundation
      version: "1"
      permissions: [query:wafers:read]
      side_effect: false
      approval_required: false
      request:
        workspace_id: TREND_PREVIEW
        table: ${state.dataset_metadata.wafer_table}
        filters:
          outlier_scopes: ${state.outliers}
      result:
        wafer_rows: ${result.rows}
        anomalous_wafers: ${result.anomalous_wafers}

  - id: approve_investigation
    type: approval
    decision_field: investigation_approved
    selection_from: outliers
    activity: Waiting for investigation approval
    approval:
      id: investigate_outlier
      required: true
      decision_field: investigation_approved
      title: Investigate selected outlier
      description: >-
        Approve reading wafer-level evidence scoped to the selected candidate
        outlier.
    payload:
      question: Investigate the selected outlier?
      approve_label: Investigate
      reject_label: Reject
      detected_outliers: ${state.outliers}
      selected_outlier: ${state.selected_outlier}
    responses:
      investigation_approved: {from: approved, type: boolean, default: false}
      selected_outlier: {from: selected_outlier_id, type: object, default: null}

  - id: investigate_selected_outlier
    type: capability
    output_to: wafer_rows
    inputs: [dataset_metadata, selected_outlier]
    activity: Reading wafer-level evidence for the selected outlier
    capability:
      operation: investigate_outlier
      server: analytics-foundation
      tool: query_wafers
      owner: Analytics Foundation
      version: "1"
      permissions: [query:wafers:read]
      side_effect: false
      approval_required: false
      request:
        workspace_id: TREND_PREVIEW
        table: ${state.dataset_metadata.wafer_table}
        filters:
          exposure_equipment_id: ${state.selected_outlier.machine}
          layer_id: ${state.selected_outlier.layer_id}
          lot_id: ${state.selected_outlier.lot_id}
      result:
        wafer_rows: ${result.rows}
        anomalous_wafers: ${result.anomalous_wafers}

  - id: classify_spatial_pattern
    type: model
    output_to: spatial_pattern
    input_projection:
      anomalous_wafers: $.anomalous_wafers
    knowledge: [wafers]
    activity: Classifying the anomalous wafer spatial pattern
    instructions: |
      Classify the supplied wafer evidence only when it supports a pattern.
      State limitations and do not infer a process cause.
    output:
      classification: {type: string, default: "", description: Evidence-based spatial pattern classification.}
      limitations: {type: string_list, default: [], description: Limitations of the spatial classification.}

  - id: summarize_findings
    type: model
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
    knowledge: [trends, outliers, wafers]
    activity: Preparing evidence-based findings
    instructions: |
      Summarize only the supplied investigation evidence.

      Do not invent identifiers, KPI definitions, causes, measurements,
      datasets, time ranges, or business semantics.

      Distinguish an observed pattern from a confirmed root cause.

      Include limitations and alternative explanations when the supplied
      evidence does not establish causality.

      When anomalous wafers are present, include the exact recommended action
      "Analyze wafer spatial pattern" in recommended_next_actions. This is the
      only currently supported follow-up action; do not imply that other
      recommendations will be executed automatically.
    output:
      finding: {type: string, default: "", description: Evidence-based investigation finding.}
      evidence_references: {type: string_list, default: [], description: References to evidence available in workflow state.}
      confidence: {type: literal, values: [low, medium, high], default: low, description: Confidence based only on available evidence.}
      limitations: {type: string_list, default: [], description: Important limitations of the investigation.}
      recommended_next_actions: {type: string_list, default: [], description: Evidence-grounded supported next actions.}
      alternative_explanations: {type: string_list, default: [], description: Plausible explanations not ruled out by the evidence.}

  - id: select_next_action
    type: approval
    decision_field: next_action_approved
    activity: Waiting for the analyst to select and approve a recommended action
    approval:
      id: select_recommended_action
      required: true
      decision_field: next_action_approved
      title: Select and approve a recommended action
      description: >
        The analyst selects one of the model's recommended actions and approves
        it before the workflow proceeds. Only supported actions are executed.
    payload:
      question: Which recommended follow-up action should I perform?
      approve_label: Approve action
      reject_label: Skip
      options: ${state.findings.recommended_next_actions}
    responses:
      next_action_approved: {from: approved, type: boolean, default: false}
      selected_action: {from: selected_action, type: optional_string, default: null}

edges:
  - {from: parse_trend_request, to: request_trend_evidence}
  - {from: request_trend_evidence, to: review_trends}
  - {from: review_trends, to: read_distribution_stats}
  - {from: read_distribution_stats, to: interpret_detection_scope}
  - {from: interpret_detection_scope, to: analyse_trends}
  - {from: confirm_threshold, to: analyse_trends_with_confirmed_threshold}
  - {from: analyse_trends, to: read_metadata}
  - {from: analyse_trends_with_confirmed_threshold, to: read_metadata}
  - {from: read_metadata, to: preview_wafers}
  - {from: preview_wafers, to: approve_investigation}
  - {from: approve_investigation, to: investigate_selected_outlier}
  - {from: investigate_selected_outlier, to: summarize_findings}
  - {from: summarize_findings, to: select_next_action}
  - {from: select_next_action, to: classify_spatial_pattern}
  - {from: classify_spatial_pattern, to: END}

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
    - {from: request_trend_evidence, when: "trend_filters.outliers_requested == true", to: read_distribution_stats}
    - {from: review_trends, when: "outlier_detection_requested == false", to: END}
    - {from: interpret_detection_scope, when: "detection_scope.suggested_limit_value != null", to: confirm_threshold}
    - {from: confirm_threshold, when: "threshold_confirmed == false", to: END}
    - {from: analyse_trends, when: "outliers == []", to: summarize_findings}
    - {from: analyse_trends_with_confirmed_threshold, when: "outliers == []", to: summarize_findings}
    - {from: approve_investigation, when: "investigation_approved == false", to: END}
    - {from: select_next_action, when: "next_action_approved == false", to: END}
    - {from: select_next_action, when: 'selected_action == "Analyze wafer spatial pattern"', to: classify_spatial_pattern}
---

# OPO Analysis Agent V1

Single-file definition for the existing trend, deterministic outlier detection,
approved wafer investigation and optional spatial-classification workflow.
Explicit edges preserve the alternate confirmed-threshold path and action routing.
The YAML anchor reuses the established trend-filter request without duplicating it.

Domain knowledge is model-facing: universal rules reach every model step and
named topics reach only selecting steps. State defaults and external response
types are retained for compatibility with existing conversations and UI evidence.
Foundation MCP tools perform deterministic data access and detection. No
application-owned capability service or workspace-creation flow is introduced.