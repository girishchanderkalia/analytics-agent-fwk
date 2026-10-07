---
id: opo-analysis-agent-v4-workflow
version: "4.0"
kind: workflow

entry_node: parse_trend_request

nodes:
  - id: parse_trend_request
    type: model
    prompt: trend_filters
    output: TrendFilters
    output_to: trend_filters
    cacheable: true
    inputs:
      - question
      - conversation_context
    activity: Interpreting the requested OPO performance window

  # Resolved by the application (BFF), which calls Analytics Foundation directly with
  # trend_filters and resumes with trend_series; the runtime never calls Foundation here.
  - id: request_trend_evidence
    type: approval
    approval: request_trend_evidence
    decision_field: trend_series
    decision_fields:
      trend_series: trend_series
    payload:
      trend_filters: ${state.trend_filters}
    activity: Reading OPO performance trends

  - id: request_tdbb_before
    type: capability
    capability: processing.run_tdbb_before
    output_to: tdbb_before_run
    inputs:
      - comparison_scope
      - trend_filters
    activity: Asking Foundation for the before-period TDBB result

  - id: request_tdbb_after
    type: capability
    capability: processing.run_tdbb_after
    output_to: tdbb_after_run
    inputs:
      - comparison_scope
      - trend_filters
    activity: Asking Foundation for the after-period TDBB result

  - id: analyze_tdbb
    type: model
    prompt: tdbb_model_analysis
    output: TdbbModelAnalysis
    output_to: tdbb_model_analysis
    input_projection:
      comparison_scope: $.comparison_scope
      before:
        change_date: $.tdbb_before_run.change_date
        periods: $.tdbb_before_run.periods
      after:
        change_date: $.tdbb_after_run.change_date
        periods: $.tdbb_after_run.periods
    activity: Analyzing the two Foundation TDBB results
  - id: suggest_change
    type: model
    prompt: change_suggestion
    output: ChangeSuggestion
    output_to: change_suggestion
    inputs:
      - trend_filters
      - trend_series
    activity: Suggesting when the OPO KPIs changed

  - id: request_comparison
    type: approval
    approval: request_tdbb_comparison
    decision_field: comparison_requested
    decision_fields:
      comparison_requested: approved
      comparison_request: comparison_request
    payload:
      question: What changed in OPO? Confirm or edit the change date; TDBB runs on all lots before and after it.
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
    activity: Waiting for the analyst to identify the OPO change

  - id: interpret_comparison
    type: model
    prompt: comparison_scope
    output: ComparisonScope
    output_to: comparison_scope
    inputs:
      - comparison_request
      - trend_filters
      - change_suggestion
    activity: Identifying the before and after periods

  # Returns the TDBB overview to the analyst before the model summary runs. The same
  # approval also collects the NCE root-cause observation (e.g. a bigger wafer-edge
  # residual) so the analyst's third prompt has a place to go without an extra gate.
  - id: review_tdbb
    type: approval
    approval: review_tdbb_results
    decision_field: tdbb_explanation_requested
    decision_fields:
      tdbb_explanation_requested: approved
      root_cause_requested: approved
      root_cause_request: root_cause_request
    payload:
      question: TDBB completed. Explain how the budgets changed, and describe what you noticed (e.g. a bigger wafer-edge residual) for a root-cause correlation.
      approve_label: Explain changes
      reject_label: Finish
      details:
        Result: ${state.tdbb_model_analysis.message}
      input:
        name: root_cause_request
        label: Your observation (e.g. which map or budget changed)
        type: text
    activity: Waiting for the analyst to review the TDBB overview and describe an NCE observation

  - id: summarize_tdbb
    type: model
    prompt: tdbb_summary
    output: TdbbSummary
    output_to: tdbb_summary
    # tdbb_before_run/tdbb_after_run also carry per-point wafer/field maps for
    # the UI overview; the summary only needs the budget numbers, so project
    # those out instead of serializing the full run result into the prompt.
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

  - id: analyze_nce_root_cause
    type: model
    prompt: nce_root_cause_analysis
    output: NceRootCauseAnalysis
    output_to: nce_root_cause_analysis
    # Same projection style as analyze_tdbb/summarize_tdbb: periods carry budgets and
    # radial_profile, not the heavy per-point maps (those stay UI-only evidence).
    input_projection:
      comparison_scope: $.comparison_scope
      root_cause_request: $.root_cause_request
      before:
        periods: $.tdbb_before_run.periods
      after:
        periods: $.tdbb_after_run.periods
    activity: Looking for a correlation between the TDBB change and the NCE residual pattern

edges:
  - from: parse_trend_request
    to: request_trend_evidence
  - from: request_trend_evidence
    to: suggest_change
  - from: suggest_change
    to: request_comparison
  - from: request_comparison
    to: interpret_comparison
  - from: interpret_comparison
    to: request_tdbb_before
  - from: request_tdbb_before
    to: request_tdbb_after
  - from: request_tdbb_after
    to: analyze_tdbb
  - from: analyze_tdbb
    to: review_tdbb
  - from: review_tdbb
    to: summarize_tdbb
  - from: summarize_tdbb
    to: analyze_nce_root_cause
  - from: analyze_nce_root_cause
    to: END

routing:
  defaults:
    request_trend_evidence: suggest_change
    suggest_change: request_comparison
    request_comparison: interpret_comparison
    interpret_comparison: request_tdbb_before
    review_tdbb: summarize_tdbb
    summarize_tdbb: analyze_nce_root_cause
    analyze_nce_root_cause: END
  conditions:
    - from: parse_trend_request
      when: "trend_filters.start_date == null"
      to: END
    - from: request_comparison
      when: "comparison_requested == false"
      to: END
    - from: interpret_comparison
      when: "comparison_scope.change_date == null"
      to: END
    - from: review_tdbb
      when: "tdbb_explanation_requested == false"
      to: END

approvals:
  - id: request_tdbb_comparison
    required: true
    decision_field: comparison_requested
    title: Run TDBB before and after a change
    description: >
      After reviewing the OPO trend, enter the change date. Approving runs
      TDBB with default settings on all lots in the window before and after
      that date.

  - id: review_tdbb_results
    required: true
    decision_field: tdbb_explanation_requested
    title: Review the TDBB overview
    description: >
      The TDBB overview is shown as soon as the runs complete, alongside the
      fingerprint, EExy and fingerprint-residual wafer maps. Approving asks
      the agent to explain the budget changes and to correlate the typed
      observation (e.g. a bigger wafer-edge residual) with the TDBB change,
      suggesting evidence-grounded next steps.

  - id: request_trend_evidence
    required: true
    decision_field: trend_series
    title: Supply Foundation trend evidence
    description: >
      Not shown to the analyst. The application resolves this automatically:
      it calls Analytics Foundation query_trends with trend_filters and
      resumes the conversation with the resulting trend_series.
---

# OPO performance and TDBB comparison (v4)

1. Ask for the OPO performance of a product, layer and scanner (optionally
   lot and chuck) since a date. A date without a year uses the current year.
   Query one calendar month from that date and show overlay X and Y KPIs
   (|mean| + 3 sigma per wafer, nm). Suggest the change date from a step in
   the daily X/Y means and prefill the follow-up question with it.
2. After the trend is shown, ask what changed and when; the analyst confirms
   or edits the prefilled question. Interpret the change date within the
   same scope and window, then run TDBB with default settings (10par, AVG
   and W2W) on all lots before and after it. Show the TDBB overview (NCE and
   CE wafer, field and translation per context level: average, chuck to
   chuck, lot to lot, wafer to wafer) as soon as the runs complete, alongside
   the fingerprint, EExy and fingerprint-residual wafer maps (rendered by the
   application from the same before/after TDBB run maps). The comparison
   localises the change; it does not establish its cause.
3. At the same step, the analyst also describes an observation about the
   wafer maps (e.g. a bigger wafer-edge residual). Approving asks the agent
   to explain the TDBB budget changes and to correlate the observation with
   the TDBB change and the residual's center-versus-edge wafer radius bands,
   suggesting evidence-grounded next steps (inspect the edge-weighted
   fingerprint, set up a new control model, simulate it in shadow mode).
   This is a temporal correlation, not a confirmed cause.
