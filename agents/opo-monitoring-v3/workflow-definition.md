---
id: opo-monitoring-workflow-v3
version: "3.0"
kind: workflow

entry_node: parse_trend_request

nodes:
  - id: parse_trend_request
    type: model
    prompt: trend_filters
    output: TrendFilters
    output_to: trend_filters
    inputs:
      - question
      - conversation_context
    activity: Interpreting the requested OPO performance window

  - id: normalize_trend_window
    type: operation
    operation: normalize_trend_window
    activity: Applying the one-month OPO window

  - id: read_trends
    type: capability
    capability: data_query.read_trends
    activity: Reading OPO performance trends

  - id: suggest_change
    type: operation
    operation: suggest_change_date
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
        value: ${state.change_suggestion.question}
    activity: Waiting for the analyst to identify the OPO change

  - id: interpret_comparison
    type: model
    prompt: comparison_scope
    output: ComparisonScope
    output_to: comparison_scope
    inputs:
      - comparison_request
      - trend_filters
    activity: Identifying the before and after periods

  - id: run_tdbb
    type: capability
    capability: processing.run_tdbb
    activity: Running TDBB before and after the change

  - id: compare_tdbb
    type: operation
    operation: compare_tdbb_budgets
    activity: Comparing TDBB budgets

  # Returns the TDBB overview to the analyst before the model summary runs.
  - id: review_tdbb
    type: approval
    approval: review_tdbb_results
    decision_field: tdbb_explanation_requested
    decision_fields:
      tdbb_explanation_requested: approved
    payload:
      question: TDBB completed. Explain how the budgets changed?
      approve_label: Explain changes
      reject_label: Finish
      details:
        Result: ${state.tdbb_comparison.headline}
    activity: Waiting for the analyst to review the TDBB overview

  - id: summarize_tdbb
    type: model
    prompt: tdbb_summary
    output: TdbbSummary
    output_to: tdbb_summary
    inputs:
      - comparison_scope
      - tdbb_comparison
    activity: Summarizing the TDBB comparison

edges:
  - from: parse_trend_request
    to: normalize_trend_window
  - from: normalize_trend_window
    to: read_trends
  - from: read_trends
    to: suggest_change
  - from: suggest_change
    to: request_comparison
  - from: request_comparison
    to: interpret_comparison
  - from: interpret_comparison
    to: run_tdbb
  - from: run_tdbb
    to: compare_tdbb
  - from: compare_tdbb
    to: review_tdbb
  - from: review_tdbb
    to: summarize_tdbb
  - from: summarize_tdbb
    to: END

routing:
  defaults:
    read_trends: suggest_change
    suggest_change: request_comparison
    request_comparison: interpret_comparison
    interpret_comparison: run_tdbb
    review_tdbb: summarize_tdbb
    summarize_tdbb: END
  conditions:
    - from: parse_trend_request
      when: "trend_filters.start_date == null"
      to: END
    - from: normalize_trend_window
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
      The TDBB overview is shown as soon as the runs complete. Approving asks
      the agent to explain the budget changes.
---

# OPO performance and TDBB comparison (v3)

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
   chuck, lot to lot, wafer to wafer) as soon as the runs complete, then
   explain the budget changes on request. The comparison localises the
   change; it does not establish its cause.
3. NCE root-cause analysis is not yet part of this workflow. The application
   reserves fingerprint, EExy and fingerprint-residual views; they stay
   placeholders until their table schemas are defined, and the agent must not
   describe their contents.
