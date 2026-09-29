---
id: opo-monitoring-v2
version: "2.0"
kind: agent

display_name: OPO-monitoring-v2

description: >
  Displays a scoped OPO performance trend and sets up an analyst-requested
  before/after TDBB comparison. TDBB measurements are not yet available.

ownership:
  owner: OPO Monitoring application
  runtime_owner: Application Agent Runtime

defaults:
  outlier_mode: baseline
  limit_value: 3.0
  baseline_deviation_pct: 3.0

conversation:
  welcome_message: >
    Ask for OPO performance by product, layer, scanner and start date. After
    reviewing the trend, tell me when you observed a jump.

  suggested_prompts:
    - Show OPO performance by product, layer and scanner since a date.
    - I observe a jump from 1 Sep to 17 Sep and want to know what changed in OPO.

context:
  accepted:
    - application_id
    - route
    - selected_lot_ids
    - selected_product_ids
    - selected_layer_ids
    - selected_equipment_ids
    - workspace_id
    - available_trend_scopes

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
        description: Inclusive ISO start date of the requested calendar month.

      end_date:
        type: optional_string
        default: null
        description: Inclusive ISO date one day before the next month's start date.

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

  ComparisonScope:
    fields:
      change_date:
        type: optional_string
        default: null
        description: ISO date when the analyst observed a change, or null if unspecified.
      interpretation:
        type: string
        default: ""
        description: Restatement of the analyst's before/after question.

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
    Extract the product, layer, scanner, and starting date from the analyst
    request. For a supplied starting date, use its ISO date as start_date and
    the day before the same date next month as inclusive end_date. Use explicit dates instead
    of lookback_days. A named scanner is an exposure equipment identifier:
    put scanner 1234 in exposure_equipment_ids as "1234", not in lot_ids.
    If the year is missing, use only entries in
    conversation_context.available_trend_scopes whose product, layer and scanner
    all match the request. Choose a year only when its requested one-month
    window overlaps a month in those matching entries. If none match, leave
    start_date and end_date null and explain that the year needs clarification
    in interpretation. Never infer a year from another product, layer, or
    scanner, or from today's date.

    Do not invent lot identifiers, product identifiers, layer identifiers,
    equipment identifiers, dates, or filter values.

    Use only information present in the analyst request or supplied application
    context.

    When a value is not present, leave the corresponding field empty or null.

    The current Foundation trend series contains one scalar OPO KPI value,
    not separate X and Y measurements. Do not claim otherwise.

  comparison_scope: |
    Interpret the analyst's follow-up question using the original trend filters
    and trend series. For a change "from 1 Sep to 17 Sep", use 1 Sep as the
    before/after boundary, NOT 17 Sep. The later date describes the observed
    after period. Resolve a missing year from trend_filters.start_date; the
    boundary must fall within the queried trend window. If it does not, or
    the date remains ambiguous, leave change_date null. Do not claim to know
    what caused the change. TDBB budgets and wafer/field measurements are
    unavailable; do not invent them or substitute OPO KPI values for TDBB data.

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