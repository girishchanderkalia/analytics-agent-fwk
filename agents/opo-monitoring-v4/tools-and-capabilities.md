---
id: opo-monitoring-capabilities-v4
version: "4.0"
kind: tools-and-capabilities

operations:
  - id: normalize_trend_window
    server: opo-capability
    tool: normalize_trend_window
    version: "1"
    owner: OPO Monitoring application
    description: >
      Resolve a missing year to the current year and apply the inclusive
      one-calendar-month window from the parsed start date.
    request:
      filters: ${state.trend_filters}
      question: ${state.question}
    result:
      trend_filters: ${result.trend_filters}

  - id: resolve_change_date
    server: opo-capability
    tool: resolve_change_date
    version: "1"
    owner: OPO Monitoring application
    description: >
      Application-owned change-date resolution: a date without a year takes
      the year that places it in the analysed window; dates outside the
      window are rejected.
    request:
      scope: ${state.comparison_scope}
      question: ${state.comparison_request}
      start_date: ${state.trend_filters.start_date}
      end_date: ${state.trend_filters.end_date}
    result:
      comparison_scope: ${result.comparison_scope}

  - id: suggest_change_date
    server: opo-capability
    tool: suggest_change_date
    version: "1"
    owner: OPO Monitoring application
    description: >
      Application-owned change-point suggestion from the daily overlay X/Y
      means, used to prefill the analyst's follow-up question.
    request:
      series: ${state.trend_series}
      end_date: ${state.trend_filters.end_date}
    result:
      change_suggestion: ${result}

  - id: compare_tdbb_budgets
    server: opo-capability
    tool: compare_tdbb_budgets
    version: "1"
    owner: OPO Monitoring application
    description: >
      Application-owned before/after comparison of TDBB budgets with the
      largest increase.
    request:
      periods: ${state.tdbb_run.periods}
    result:
      tdbb_comparison: ${result}

capabilities:
  - id: data_query.read_trends
    operation: read_trends
    server: analytics-foundation
    tool: query_trends
    owner: Analytics Foundation
    version: "1"
    permissions:
      - query:trends:read
    side_effect: false
    approval_required: false
    request:
      days: ${state.trend_filters.lookback_days}
      start_date: ${state.trend_filters.start_date}
      end_date: ${state.trend_filters.end_date}
      lot_ids: ${state.trend_filters.lot_ids}
      product_ids: ${state.trend_filters.product_ids}
      layer_ids: ${state.trend_filters.layer_ids}
      exposure_equipment_ids: ${state.trend_filters.exposure_equipment_ids}
      chuck_ids: ${state.trend_filters.chuck_ids}
    result:
      trend_series: ${result.series}

  - id: processing.run_tdbb
    operation: run_tdbb
    server: analytics-foundation
    tool: run_tdbb
    owner: Analytics Foundation
    version: "1"
    permissions:
      - processing:tdbb:run
    side_effect: true
    # Approved at the request_comparison gate.
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
      tdbb_run: ${result}

  - id: analysis.compare_tdbb_runs
    operation: compare_tdbb_runs
    server: analytics-foundation
    tool: compare_tdbb_runs
    owner: Analytics Foundation
    version: "1"
    permissions:
      - query:tdbb:read
    side_effect: false
    approval_required: false
    request:
      before_run_ids: ${state.tdbb_run.periods[0].run_ids}
      after_run_ids: ${state.tdbb_run.periods[1].run_ids}
    result:
      tdbb_model_evidence: ${result}
---

# V4 data boundaries

The OPO capability normalizes the model's trend window before the governed
Foundation query. TDBB runs through Analytics Foundation with its default
settings (10par, AVG and W2W); in the mock Foundation the request resolves to
existing per-lot TDBB runs, whose rows are available through `get_tdbb_data`.
The before/after budget comparison is application-owned logic in the OPO
capability service. The v4 model analysis also receives a read-only Foundation
comparison by the before and after run IDs returned by `run_tdbb`; Foundation
computes the canonical summaries, X/Y deltas, percentages, largest increase
and headline.

Example request:

```json
{"before_run_ids":["run-LotOV1001"],"after_run_ids":["run-LotOV1003"]}
```

Example response shape:

```json
{"before":{"period":"before","run_ids":["run-LotOV1001"],"lot_count":1,"wafer_count":2,"budgets":[...]},"after":{"period":"after","run_ids":["run-LotOV1003"],"lot_count":1,"wafer_count":2,"budgets":[...]},"budgets":[{"budget":"nce_wafer.average","before_x":0.75,"after_x":1.52,"delta_x":0.77,"delta_x_pct":102.7,"before_y":0.62,"after_y":0.81,"delta_y":0.19,"delta_y_pct":30.6}],"largest_increase":{"budget":"nce_wafer.average","axis":"X","delta":0.77,"delta_pct":102.7},"headline":"Largest increase: NCE - Wafer · Average X +102.7%"}
```
