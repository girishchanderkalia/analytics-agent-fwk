---
id: opo-monitoring-workflow-v2
version: "2.0"
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

  - id: read_trends
    type: capability
    capability: data_query.read_trends
    activity: Reading OPO performance trends

  - id: normalize_trend_window
    type: operation
    operation: normalize_trend_window
    activity: Applying the one-month OPO window

  - id: request_comparison
    type: approval
    approval: request_tdbb_comparison
    decision_field: comparison_requested
    decision_fields:
      comparison_requested: approved
      comparison_request: comparison_request
    payload:
      question: What changed in OPO? Enter the date of the jump to compare before and after.
      approve_label: Compare periods
      reject_label: Finish
      details:
        Filters: ${state.trend_filters.interpretation}
      input:
        name: comparison_request
        label: Your question (include the change date)
        type: text
        value: ""
    activity: Waiting for the analyst to identify the OPO change

  - id: interpret_comparison
    type: model
    prompt: comparison_scope
    output: ComparisonScope
    output_to: comparison_scope
    inputs:
      - comparison_request
      - trend_filters
      - trend_series
    activity: Identifying the before and after periods

edges:
  - from: parse_trend_request
    to: normalize_trend_window
  - from: normalize_trend_window
    to: read_trends
  - from: read_trends
    to: request_comparison
  - from: request_comparison
    to: interpret_comparison
  - from: interpret_comparison
    to: END

routing:
  defaults:
    read_trends: request_comparison
    request_comparison: interpret_comparison
    interpret_comparison: END
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

approvals:
  - id: request_tdbb_comparison
    required: true
    decision_field: comparison_requested
    title: Compare OPO before and after a change
    description: >
      After reviewing the OPO trend, enter a change date. TDBB processing
      and measurements are not yet available in Analytics Foundation.
---

# OPO performance and TDBB comparison (v2)

1. Ask for the OPO performance of a product, layer, and scanner since a date.
   Query the following calendar month using the supplied filters. Display the
   available OPO KPI trend; the current Foundation contract has no separate
   OPO X and Y measurements, so never label the scalar KPI as X or Y.
2. After the trend is shown, ask what changed and when. Interpret the date
   within the same product/layer/scanner scope. The application reserves two
   TDBB views: a before/after budget bar comparison and wafer/field plots per
   budget. Both remain explicitly unavailable until a TDBB processing
   interface and real measurements exist. Do not calculate or invent TDBB
   budgets, bars, spatial points, or causal conclusions from the OPO KPI.