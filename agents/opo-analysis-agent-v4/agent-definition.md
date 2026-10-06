---
id: opo-analysis-agent-v4
version: "V4"
kind: agent

display_name: OPO Analysis Agent

description: >
  Displays a scoped OPO performance trend (overlay X and Y in nm) and, for an
  analyst-observed jump, runs TDBB with default settings on all lots before
  and after the jump and reports how the budgets changed.

ownership:
  owner: OPO Monitoring application
  runtime_owner: Application Agent Runtime

defaults:
  outlier_mode: baseline
  limit_value: 3.0
  baseline_deviation_pct: 3.0

conversation:
  welcome_message: >
    Ask for OPO performance by product, layer, scanner (optionally lot and
    chuck) and start date. After reviewing the trend, tell me when you
    observed a jump and I will compare TDBB budgets before and after it.

  suggested_prompts:
    - Show OPO performance of product AAA2, layer OV_NO_ID2 on scanner GW021 since 17 Aug.
    - I observe a jump from 1 Sep to 17 Sep and want to know what changed in OPO.
    - I observe that the wafer NCE in average gets bigger after 1 Sep. What could cause this change?

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

      chuck_ids:
        type: string_list
        default: []
        description: Wafer stage chuck identifiers, e.g. "Waferstage chuck ID 1".

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

  TdbbSummary:
    fields:
      message:
        type: string
        default: ""
        description: Short analyst-facing message on the TDBB before/after comparison.
      largest_change:
        type: string
        default: ""
        description: The budget and axis with the largest relative increase, with before/after values.
      limitations:
        type: string_list
        default: []
        description: Limitations of the TDBB comparison.

  TdbbModelAnalysis:
    fields:
      message:
        type: string
        default: ""
        description: Evidence-based interpretation of the Foundation TDBB comparison.
      largest_change:
        type: string
        default: ""
        description: Largest Foundation-reported budget increase.
      limitations:
        type: string_list
        default: []
        description: Limitations supported by the returned TDBB evidence.

  NceRootCauseAnalysis:
    fields:
      message:
        type: string
        default: ""
        description: >
          Evidence-grounded explanation of where the NCE change is concentrated
          (metric, context level, and center-versus-edge wafer radius band),
          using only the supplied TDBB budget and radial-profile numbers.
      correlated_evidence:
        type: string_list
        default: []
        description: >
          The specific supplied values that support the correlation (e.g. a
          named budget's before/after numbers, or a center/edge band delta).
      recommended_next_actions:
        type: string_list
        default: []
        description: Evidence-grounded next steps, not automatically executed.
      limitations:
        type: string_list
        default: []
        description: Limitations of this root-cause analysis.

  ChangeSuggestion:
    fields:
      change_date:
        type: optional_string
        default: null
        description: Date where the supplied trend evidence changes.
      question:
        type: string
        default: ""
        description: Prefilled analyst follow-up question.

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
    Extract the product, layer, scanner, optional lot and chuck, and starting
    date from the analyst request. For a supplied starting date, use its ISO
    date as start_date. Unless the analyst also names an explicit end date,
    use conversation_context.current_date (today's date) as the inclusive
    end_date, so the trend covers the starting date through today. Use
    explicit dates instead of lookback_days. A named scanner is an exposure
    equipment identifier: put scanner GW021 in exposure_equipment_ids as
    "GW021", not in lot_ids. A named chuck is a
    wafer stage chuck: put chuck 1 in chuck_ids as "Waferstage chuck ID 1".
    Leave lot_ids and chuck_ids empty unless the analyst explicitly names a
    lot or chuck; the default is all lots and both chucks.
    If the analyst omits the year, still return an ISO date; use the year from
    conversation_context.current_date. If no starting date is given,
    leave start_date and end_date null and explain in interpretation.

    Do not invent lot identifiers, product identifiers, layer identifiers,
    equipment identifiers, chuck identifiers, dates, or filter values.

    Use only information present in the analyst request or supplied application
    context.

    When a value is not present, leave the corresponding field empty or null.

    The trend series contains overlay X (kpi_value) and Y (kpi_value_y) KPIs
    per wafer, each |mean| + 3 sigma in nm.

  comparison_scope: |
    Interpret the analyst's follow-up question using the original trend
    filters. For a change "from 1 Sep to 17 Sep", use 1 Sep as the
    before/after boundary, NOT 17 Sep. The later date describes the observed
    after period.

    If the follow-up question contains no date but the supplied
    change_suggestion has a change_date, use that suggested date as the
    boundary. This is the analyst accepting the prefilled follow-up question;
    do not return a null change_date in that case.

    If the analyst does not specify a year, take the current year: the year
    of trend_filters.start_date, or of trend_filters.end_date when the
    analysed month crosses a year boundary. Never leave change_date null only
    because the year is missing, and do not ask for the year. Always return
    the named boundary as an ISO date; the application then checks that it
    falls after trend_filters.start_date and not later than
    trend_filters.end_date. Leave change_date null only when the analyst names
    no date at all, and explain that in interpretation. Do not claim to know
    what caused the change.

  trend_evidence: |
    Keep the extracted trend filters unchanged and request matching trend
    evidence through the query_trends tool. Use only those filters and return
    the same TrendFilters JSON after the tool call.

  change_suggestion: |
    Inspect the supplied trend evidence and suggest a visible change date only
    when a clear step is present. Do not invent a date or claim causality.
    Return a short prefilled follow-up question when a date is suggested.

  tdbb_summary: |
    Write a short message for the analyst about the two TDBB results in
    tdbb_runs. TDBB was run with default settings (10par model, AVG and
    W2W context levels) on all lots before and after the change date within
    the analysed month. Each budget is one cell of the TDBB overview: a metric
    (NCE - Wafer, NCE - Field, CE - Wafer, CE - Field, CE - Translation) at a
    context level (Average, Chuck to chuck, Lot to lot, Wafer to wafer).
    Start with one sentence on both periods (dates, lots, wafers). The
    message must then contain exactly four markdown bullet lines, in this
    order: "- Average: ...", "- Chuck to chuck: ...", "- Lot to lot: ...",
    "- Wafer to wafer: ...". In each bullet name the metrics whose X or Y
    value changed by more than 20%, with before and after values in nm and the
    change in percent, or write "no change above 20%" when none did.
    Use only the supplied numbers. The values are |mean| + 3 sigma; never
    call them a mean. Name largest_increase as the largest relative increase.
    If a period has no lots, say that TDBB data is missing for it and do not
    compare.

    A larger budget shows where the overlay change sits (e.g. non-correctable
    versus correctable, wafer-to-wafer, chuck-to-chuck or lot-to-lot); it does
    not establish the cause. Do not name root causes, tools or process steps.

  tdbb_model_analysis: |
    Analyze the compact before and after TDBB budget evidence supplied in the
    input. Explain where the observed change is concentrated using only the
    supplied values. Do not recalculate or invent budget deltas, name a root
    cause, or claim that TDBB establishes causation. Return only concise JSON
    matching TdbbModelAnalysis.

  tdbb_before_request: |
    You must call the provided run_tdbb tool exactly once for the before period
    before returning JSON. Use the established trend filters and change date;
    request the period before the change. Do not answer from memory or invent
    TDBB values. Return a concise placeholder TdbbModelAnalysis after the tool
    call; the returned tool evidence is the source of truth.

  tdbb_after_request: |
    You must call the provided run_tdbb tool exactly once for the after period
    before returning JSON. Use the established trend filters and change date;
    request the period after the change. Do not answer from memory or invent
    TDBB values. Return a concise placeholder TdbbModelAnalysis after the tool
    call; the returned tool evidence is the source of truth.

  nce_root_cause_analysis: |
    The analyst observed the TDBB comparison and typed root_cause_request, an
    observation or question about the NCE change (for example: the wafer NCE
    in average gets bigger after 1 Sep, what could cause this). Answer using
    only the supplied before/after TDBB budgets and radial_profile bands.

    First localise the change: compare nce_wafer.average (non-correctable
    residual) against ce_wafer.average (correctable fingerprint) before and
    after the change date. When nce_wafer.average rose sharply while
    ce_wafer.average stayed roughly flat, say so explicitly - this means the
    change is not an exposure-correction (fingerprint) issue.

    Then inspect radial_profile for nce_wafer.average: compare the center and
    edge band m3s values before and after. When the edge band's increase is
    proportionally larger than the center band's, state that the residual
    growth concentrates near the wafer edge, in the same before/after window
    as the analyst's observation. Treat this as a temporal correlation with
    the OPO trend jump, not a proven cause.

    recommended_next_actions must contain, in this order, only these three
    evidence-motivated next steps, each one short sentence: (1) inspect the
    edge-weighted fingerprint/exposure process around
    comparison_scope.change_date for a bigger edge component, naming the
    edge-band numbers found; (2) propose setting up a new control model that
    captures the edge-weighted residual pattern; (3) propose simulating that
    new control model in shadow mode before enabling it in production. Do not
    add other actions.

    Do not claim the correlation is a confirmed root cause. Do not invent
    budgets, bands, or numbers beyond what is supplied.

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
  - comparison_scope
  - tdbb_run
  - tdbb_comparison
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
  - Report TDBB budgets only from the TDBB comparison evidence.
  - Restrict findings to evidence available in workflow state.
  - Require approval before operations marked as approval-required.
---

# OPO Analysis Agent

The OPO Analysis Agent interprets analyst requests, coordinates governed
Analytics Foundation capabilities, and produces evidence-based findings.

Model calls are limited to interpretation and summarization. Deterministic
analysis is executed by application operations. Platform operations and side
effects are performed through declared runtime capabilities.