---
id: opo-analysis-agent-v4
version: "V4"
kind: agent
display_name: OPO Analysis Agent V4
description: >
  Shows scoped overlay X/Y trends, compares TDBB evidence before and after an
  analyst-observed change, and localises supported NCE residual changes.
ownership:
  owner: OPO Monitoring application
  runtime_owner: Application Agent Runtime
conversation:
  welcome_message: >
    Ask for OPO performance by product, layer, scanner and start date.
    After reviewing the trend, confirm the change date to compare TDBB budgets.
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

knowledge:
  always: |
    Use only supplied application context and evidence. Do not invent identifiers,
    measurements, datasets, time ranges, domain definitions or process relationships.
    Runtime status and conversation metadata are operational context, not domain evidence.
    Separate observations, temporal correlations and possible explanations from
    confirmed causes. A plausible explanation remains unconfirmed without additional evidence.
    State missing evidence and limitations explicitly. High confidence in an observation
    does not imply that its cause is known. Do not claim to execute recommended actions.
  topics:
    overlay: |
      OPO trend rows contain per-wafer overlay X (kpi_value) and Y (kpi_value_y).
      Both KPIs are |mean| + 3 sigma, expressed in nm, not plain means.
      A scanner is an exposure equipment identifier. Chuck 1 is represented as
      "Waferstage chuck ID 1". Empty lot/chuck filters mean all lots/both chucks.
      Relative or yearless dates must be grounded in supplied application dates.
    tdbb: |
      Analytics Foundation supplies TDBB results using default 10par, AVG and W2W settings.
      Budgets are |mean| + 3 sigma in nm. NCE denotes non-correctable residual;
      CE denotes correctable components. Metrics include wafer, field and translation
      components at Average, Chuck to chuck, Lot to lot and Wafer to wafer context levels.
      Compare matching metrics, axes and context levels. A larger budget localises
      an overlay change but does not establish its cause. A period with no lots
      has missing TDBB evidence, not zero overlay. Percentage change from a zero
      baseline is undefined; do not report a fabricated percentage.
    nce_radial: |
      nce_wafer.average represents a non-correctable wafer residual;
      ce_wafer.average represents a correctable wafer fingerprint component.
      Radial-profile center and edge band m3s values describe residual distribution.
      Disproportionate edge growth supports localisation near the wafer edge.
      NCE growth with roughly flat CE does not by itself prove or exclude a physical cause.
      Coincident changes in a trend and radial profile are temporal correlations.

state:
  conversation_id:
    type: optional_string
    default: null
    description: Public conversation identifier; not measurement evidence.
  current_activity:
    type: optional_string
    default: null
  question:
    type: string
    default: ""
    description: Current analyst request.
  conversation_context:
    type: object
    default: {}
    description: Application-supplied context, including current_date for date interpretation.

steps:
  - id: parse_trend_request
    type: model
    output_to: trend_filters
    description: Filters extracted from the analyst request; empty lot/chuck lists mean unrestricted scope.
    inputs: [question, conversation_context]
    knowledge: [overlay]
    cacheable: true
    activity: Interpreting the requested OPO performance window
    instructions: |
      Extract product, layer, scanner, optional lot/chuck and the starting date.
      Use ISO dates. Unless an explicit end date is given, use
      conversation_context.current_date as the inclusive end date. Use explicit
      dates instead of lookback_days. For a yearless date use the supplied current year.
      Put scanner GW021 in exposure_equipment_ids, not lot_ids. Map chuck 1 to
      "Waferstage chuck ID 1". Leave lot_ids/chuck_ids empty unless explicitly named.
      If no starting date is supplied, leave start_date/end_date null and explain why.
      Use only the analyst request and supplied context; do not invent filter values.
    output:
      lookback_days: {type: optional_int, default: null, description: Relative period only if explicitly named.}
      start_date: {type: optional_string, default: null, description: Inclusive ISO start date supplied by the analyst.}
      end_date: {type: optional_string, default: null, description: Inclusive explicit end date or supplied current date.}
      lot_ids: {type: string_list, default: [], description: Explicitly selected lot identifiers.}
      product_ids: {type: string_list, default: [], description: Selected product identifiers.}
      layer_ids: {type: string_list, default: [], description: Selected layer identifiers.}
      exposure_equipment_ids: {type: string_list, default: [], description: Selected scanner identifiers.}
      chuck_ids: {type: string_list, default: [], description: Selected wafer stage chuck identifiers.}
      interpretation: {type: string, default: "", description: Short interpretation of the requested filters.}
      outliers_requested: {type: boolean, default: false, description: Whether the request explicitly asks for anomalies or thresholds.}

  - id: request_trend_evidence
    type: approval
    activity: Reading OPO performance trends
    approval:
      id: request_trend_evidence
      required: true
      title: Supply Foundation trend evidence
      description: Application-resolved handoff; the BFF queries Foundation directly and resumes with trend rows.
    payload:
      trend_filters: ${state.trend_filters}
    responses:
      trend_series:
        from: trend_series
        type: object_list
        default: []
        description: Foundation per-wafer overlay X/Y evidence in nm; not model-generated measurements.

  - id: suggest_change
    type: model
    output_to: change_suggestion
    description: Suggested change date and follow-up question grounded in the trend evidence.
    inputs: [trend_filters, trend_series]
    knowledge: [overlay]
    activity: Suggesting when the OPO KPIs changed
    instructions: |
      Inspect the supplied trend evidence and suggest a visible change date only
      when a clear step is present. Do not invent a date or claim causality.
      Return a short prefilled follow-up question when a date is suggested.
    output:
      change_date: {type: optional_string, default: null, description: Evidence-supported ISO change date or null.}
      question: {type: string, default: "", description: Prefilled analyst follow-up question.}

  - id: request_comparison
    type: approval
    activity: Waiting for the analyst to identify the OPO change
    approval:
      id: request_tdbb_comparison
      required: true
      title: Run TDBB before and after a change
      description: Confirm or edit the change date before running TDBB within the selected scope.
    payload:
      question: What changed in OPO? Confirm or edit the change date to run TDBB within the selected scope.
      approve_label: Run TDBB
      reject_label: Finish
      details:
        Filters: ${state.trend_filters.interpretation}
        Window: ${state.trend_filters.start_date}
        Suggested change date: ${state.change_suggestion.change_date}
        TDBB settings: 10par model, AVG and W2W context levels
      input:
        name: comparison_request
        label: Your question (include the change date)
        type: text
        placeholder: Enter a date here if you want to change the suggested one
        required: false
    responses:
      comparison_requested: {from: approved, type: boolean, default: false}
      comparison_request: {from: comparison_request, type: string, default: "", description: Analyst follow-up describing the observed change.}

  - id: interpret_comparison
    type: model
    output_to: comparison_scope
    description: Analyst-confirmed ISO change date separating before and after periods.
    inputs: [comparison_request, trend_filters, change_suggestion]
    knowledge: [overlay]
    activity: Identifying the before and after periods
    instructions: |
      Interpret the follow-up within the established trend filters. For a change
      "from 1 Sep to 17 Sep", use 1 Sep as the boundary, not 17 Sep.
      If the follow-up has no date but change_suggestion.change_date is present,
      use the suggested date. For a yearless date use the year of
      trend_filters.start_date, or end_date when the window crosses a year boundary.
      Return an ISO date; the application checks that it is after start_date
      and no later than end_date. Return null only if no date can be established.
      Explain the interpretation without claiming a cause.
    output:
      change_date: {type: optional_string, default: null, description: ISO before/after boundary or null if unavailable.}
      interpretation: {type: string, default: "", description: Restatement of the before/after question.}

  - id: request_tdbb_before
    type: capability
    output_to: tdbb_before_run
    description: Foundation before-period TDBB result; budgets are in nm and maps are UI evidence.
    inputs: [comparison_scope, trend_filters]
    activity: Asking Foundation for the before-period TDBB result
    capability:
      operation: run_tdbb
      server: analytics-foundation
      tool: run_tdbb
      version: "1"
      permissions: [processing:tdbb:run]
      side_effect: true
      approval_required: true
      request:
        start_date: ${state.trend_filters.start_date}
        end_date: ${state.comparison_scope.change_date}
        change_date: ${state.comparison_scope.change_date}
        lot_ids: ${state.trend_filters.lot_ids}
        product_ids: ${state.trend_filters.product_ids}
        layer_ids: ${state.trend_filters.layer_ids}
        exposure_equipment_ids: ${state.trend_filters.exposure_equipment_ids}
        chuck_ids: ${state.trend_filters.chuck_ids}
      result:
        tdbb_before_run: ${result}

  - id: request_tdbb_after
    type: capability
    output_to: tdbb_after_run
    description: Foundation after-period TDBB result with the same units and budget semantics as before.
    inputs: [comparison_scope, trend_filters]
    activity: Asking Foundation for the after-period TDBB result
    capability:
      operation: run_tdbb
      server: analytics-foundation
      tool: run_tdbb
      version: "1"
      permissions: [processing:tdbb:run]
      side_effect: true
      approval_required: true
      request:
        start_date: ${state.trend_filters.start_date}
        end_date: ${state.trend_filters.end_date}
        change_date: ${state.comparison_scope.change_date}
        lot_ids: ${state.trend_filters.lot_ids}
        product_ids: ${state.trend_filters.product_ids}
        layer_ids: ${state.trend_filters.layer_ids}
        exposure_equipment_ids: ${state.trend_filters.exposure_equipment_ids}
        chuck_ids: ${state.trend_filters.chuck_ids}
      result:
        tdbb_after_run: ${result}

  - id: analyze_tdbb
    type: model
    output_to: tdbb_model_analysis
    description: Model interpretation of the supplied Foundation budget evidence, not an independent measurement.
    knowledge: [tdbb]
    input_projection:
      comparison_scope: $.comparison_scope
      before:
        change_date: $.tdbb_before_run.change_date
        periods: $.tdbb_before_run.periods
      after:
        change_date: $.tdbb_after_run.change_date
        periods: $.tdbb_after_run.periods
    activity: Analyzing the two Foundation TDBB results
    instructions: |
      Explain where the observed change is concentrated using only supplied budgets.
      Do not invent deltas or claim causation. Prefer Foundation-reported changes
      where supplied; state limitations when the evidence lacks comparable values.
      Return concise structured output.
    output:
      message: {type: string, default: "", description: Evidence-based interpretation of the before/after comparison.}
      largest_change: {type: string, default: "", description: Largest supported budget increase with metric and axis.}
      limitations: {type: string_list, default: [], description: Limitations supported by the evidence.}

  - id: review_tdbb
    type: approval
    activity: Waiting for the analyst to review the TDBB overview and describe an NCE observation
    approval:
      id: review_tdbb_results
      required: true
      title: Review the TDBB overview
      description: Review the returned budgets and maps before requesting an explanation and residual correlation.
    payload:
      question: TDBB completed. Explain the budget changes and describe your NCE observation for a correlation analysis.
      approve_label: Explain changes
      reject_label: Finish
      details:
        Result: ${state.tdbb_model_analysis.message}
      input:
        name: root_cause_request
        label: Your observation (e.g. which map or budget changed)
        type: text
    responses:
      tdbb_explanation_requested: {from: approved, type: boolean, default: false}
      root_cause_requested: {from: approved, type: boolean, default: false}
      root_cause_request: {from: root_cause_request, type: string, default: "", description: Analyst observation; not independently verified evidence.}

  - id: summarize_tdbb
    type: model
    output_to: tdbb_summary
    description: Analyst-facing summary of the supplied TDBB budgets and supported changes.
    knowledge: [tdbb]
    input_projection:
      comparison_scope: $.comparison_scope
      tdbb_model_analysis: $.tdbb_model_analysis
      before:
        change_date: $.tdbb_before_run.change_date
        periods: $.tdbb_before_run.periods
      after:
        change_date: $.tdbb_after_run.change_date
        periods: $.tdbb_after_run.periods
    activity: Summarizing the TDBB comparison
    instructions: |
      Summarize the supplied before/after results within the selected scope.
      Start with one sentence on period dates, lots and wafers. Then give exactly
      four markdown bullet lines in order: "- Average: ...", "- Chuck to chuck: ...",
      "- Lot to lot: ...", "- Wafer to wafer: ...". In each bullet name metrics
      whose X/Y value changed by more than 20%, with before/after nm values and
      percentage change; otherwise write "no change above 20%". Use supplied
      changes or calculate only from matching supplied before/after numbers.
      Do not divide by a zero baseline. Report missing or non-comparable evidence
      instead of asserting no change. Identify the largest supported relative increase.
      Do not call budgets means, name root causes or imply that recommendations execute.
    output:
      message: {type: string, default: "", description: Short analyst-facing comparison with four context-level bullets.}
      largest_change: {type: string, default: "", description: Largest relative increase with metric and axis plus before/after values.}
      limitations: {type: string_list, default: [], description: Missing evidence and comparison limitations.}

  - id: analyze_nce_root_cause
    type: model
    output_to: nce_root_cause_analysis
    description: Correlation between supplied NCE budgets and radial profiles; not a confirmed root cause.
    knowledge: [tdbb, nce_radial]
    input_projection:
      comparison_scope: $.comparison_scope
      root_cause_request: $.root_cause_request
      before:
        periods: $.tdbb_before_run.periods
      after:
        periods: $.tdbb_after_run.periods
    activity: Looking for a correlation between the TDBB change and the NCE residual pattern
    instructions: |
      Answer the analyst observation using only supplied budgets and radial_profile bands.
      Compare nce_wafer.average with ce_wafer.average before and after the change.
      If NCE rises while CE stays roughly flat, describe the concentration in the
      non-correctable residual; do not categorically exclude exposure-process causes.
      Compare center and edge band m3s values. State edge concentration only if
      supported, and describe coincidence with the trend jump as temporal correlation.
      If edge growth is supported, recommend in order: inspect the edge-weighted
      fingerprint/exposure process around the change date using the actual band
      numbers; propose a control model capturing that residual pattern; propose
      shadow-mode simulation before production. These are recommendations, not actions.
      When budgets or radial bands are missing, report limitations instead of
      fabricating localisation or forcing an edge-specific recommendation.
    output:
      message: {type: string, default: "", description: Evidence-grounded localisation and correlation, not proven causation.}
      correlated_evidence: {type: string_list, default: [], description: Exact supplied budget or radial-band values supporting the interpretation.}
      recommended_next_actions: {type: string_list, default: [], description: Conditional evidence-grounded recommendations; never automatically executed.}
      limitations: {type: string_list, default: [], description: Missing evidence and limits on causal interpretation.}

routing:
  conditions:
    - {from: parse_trend_request, when: "trend_filters.start_date == null", to: END}
    - {from: request_comparison, when: "comparison_requested == false", to: END}
    - {from: interpret_comparison, when: "comparison_scope.change_date == null", to: END}
    - {from: review_tdbb, when: "tdbb_explanation_requested == false", to: END}
---

# OPO Analysis Agent V4

Consolidated single-file agent replacing the legacy v4 bundle. Step order defines the normal execution path;
only early-exit conditions are explicit. Domain knowledge is model-facing:
`always` reaches every model step and named topics reach only selecting steps.

Trend evidence is supplied through the existing application/BFF handoff.
TDBB operations remain governed Foundation MCP calls after analyst approval.
Raw maps stay available for the application, but model projections include
only budgets and radial profiles. Dashboard Q&A is not part of this workflow.