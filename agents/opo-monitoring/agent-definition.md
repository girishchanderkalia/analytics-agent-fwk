---
id: opo-monitoring-agent
version: "1.0"
kind: agent

display_name: OPO Monitoring Agent

description: >
  Supports conversational investigation of OPO KPI trends, candidate
  outliers, and wafer-level evidence using governed Analytics Foundation
  capabilities.

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

models:
  TrendFilters:
    fields:
      lookback_days:
        type: optional_int
        default: null
        description: >
          Relative lookback period in days. Leave null unless the analyst names
          a period; a guessed window hides older evidence.

      start_date:
        type: optional_string
        default: null
        description: Inclusive ISO start date.

      end_date:
        type: optional_string
        default: null
        description: Inclusive ISO end date.

      lot_ids:
        type: string_list
        default: []
        description: Lot identifiers selected for trend analysis.

      product_ids:
        type: string_list
        default: []
        description: Product identifiers selected for trend analysis.

      layer_ids:
        type: string_list
        default: []
        description: Layer identifiers selected for trend analysis.

      exposure_equipment_ids:
        type: string_list
        default: []
        description: Exposure equipment identifiers.

      interpretation:
        type: string
        default: ""
        description: Short interpretation of the requested filters.

      outliers_requested:
        type: boolean
        default: false
        description: >
          True when the request already asks for outliers, anomalies,
          extreme values, or a threshold; false for a trend display request.

  DetectionScope:
    fields:
      mode:
        type: literal
        values:
          - absolute
          - baseline
        default: baseline
        description: Outlier detection mode.

      limit_value:
        type: float
        default: 3.0
        description: Absolute KPI threshold used in absolute mode.

      direction:
        type: literal
        values:
          - below
          - above
        default: below
        description: Direction used to identify threshold violations.

      threshold_unit:
        type: literal
        values:
          - percent
          - absolute
        default: percent
        description: Unit used for the threshold.

      baseline_deviation_pct:
        type: optional_float
        default: null
        description: Allowed percentage deviation from the baseline.

      interpretation:
        type: string
        default: ""
        description: Short interpretation of the outlier request.

      suggested_limit_value:
        type: optional_float
        default: null
        description: Recommended absolute cutoff when clarification is needed.

      suggested_limit_rationale:
        type: optional_string
        default: null
        description: Evidence-based explanation of the suggested cutoff.

  FindingsSummary:
    fields:
      finding:
        type: string
        default: ""
        description: Evidence-based investigation finding.

      evidence_references:
        type: string_list
        default: []
        description: References to evidence available in workflow state.

      confidence:
        type: literal
        values:
          - low
          - medium
          - high
        default: low
        description: Confidence based only on available evidence.

      limitations:
        type: string_list
        default: []
        description: Important limitations of the investigation.

      recommended_next_actions:
        type: string_list
        default: []
        description: Evidence-grounded supported next actions.

      alternative_explanations:
        type: string_list
        default: []
        description: Plausible explanations not ruled out by the evidence.

prompts:
  trend_filters: |
    Extract trend filters from the analyst request.

    Do not invent lot identifiers, product identifiers, layer identifiers,
    equipment identifiers, dates, or filter values.

    Use only information present in the analyst request or supplied application
    context.

    When a value is not present, leave the corresponding field empty or null.

    Set outliers_requested to true only when the request asks for outliers,
    anomalies, extreme values, or names a threshold; otherwise set it to false
    so the analyst can review the trend chart first.

  detection_scope: |
    Interpret the analyst's outlier request within the established trend filters.
    Do not re-extract or change those filters. A number with % is a percentage
    threshold; a unitless number is an absolute OPO KPI threshold. An explicit
    numeric threshold takes precedence: leave suggested_limit_value and
    suggested_limit_rationale null when one was given.

    For a request without an explicit numeric threshold, call the
    get_distribution_stats tool before recommending an absolute OPO KPI cutoff.
    Call it at most once, with exactly the established trend filters; never
    invent another filter. Use only the tool's p95, p99, mean, stdev and
    bell_curve_range values; never invent or estimate distribution statistics.
    Recommend p95 by default and p99 only for severe anomaly detection.
    Set suggested_limit_value and suggested_limit_rationale from that evidence,
    and set mode to absolute, limit_value to the suggested value, direction to
    above, and threshold_unit to absolute. Never leave limit_value empty when
    recommending a cutoff.

    If sample_count is zero, leave suggested_limit_value null and explain the
    missing data in suggested_limit_rationale. If the tool fails or is
    unavailable, leave both suggestion fields null; do not guess a cutoff.
    Do not claim that a threshold violation establishes a root cause.

  findings_summary: |
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

evidence_labels:
  - trend_filters
  - trend_series
  - detection_scope
  - analysis
  - outliers
  - selected_outlier
  - applied_filters
  - workspace
  - registration
  - anomalous_wafers
  - wafer_rows
  - spatial_pattern

guardrails:
  - Do not access Analytics Foundation data stores directly.
  - Use declared capabilities for Analytics Foundation interactions.
  - Do not invent KPI definitions, datasets, identifiers, or measurements.
  - Do not present a plausible explanation as a confirmed cause.
  - Restrict findings to evidence available in workflow state.
  - Require approval before operations marked as approval-required.
---

# OPO Monitoring Agent

The OPO Monitoring Agent interprets analyst requests, coordinates governed
Analytics Foundation capabilities, and produces evidence-based findings.

Model calls are limited to interpretation and summarization. Deterministic
analysis is executed by application operations. Platform operations and side
effects are performed through declared runtime capabilities.