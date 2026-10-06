---
id: opo-analysis-agent-v4-capabilities
version: "4.0"
kind: tools-and-capabilities

capabilities:
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

  - id: processing.run_tdbb_before
    operation: run_tdbb
    server: analytics-foundation
    tool: run_tdbb
    owner: Analytics Foundation
    version: "1"
    permissions:
      - processing:tdbb:run
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
      tdbb_run: ${result}

  - id: processing.run_tdbb_after
    operation: run_tdbb
    server: analytics-foundation
    tool: run_tdbb
    owner: Analytics Foundation
    version: "1"
    permissions:
      - processing:tdbb:run
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
      tdbb_run: ${result}
---

# V4 data boundaries

The model extracts the trend filters; `query_trends` is not an MCP capability
in v4. Instead, `request_trend_evidence` is an approval/interrupt node: the
runtime pauses with `trend_filters` as its payload, the application (BFF)
calls Analytics Foundation `query_trends` directly with those filters, and
resumes the conversation with the resulting `trend_series`; this is resolved
automatically by the BFF and never shown to the analyst as an approval. TDBB
still runs through Analytics Foundation with its default settings (10par, AVG
and W2W) as an MCP capability: after the analyst approves, the model requests
one `run_tdbb` result for each period through MCP and analyzes the two
returned results. There is no application-owned MCP service and no
`compare_tdbb_runs` call in v4.

Example request:

```json
{"before_run_ids":["run-LotOV1001"],"after_run_ids":["run-LotOV1003"]}
```

Example response shape:

```json
{"before":{"period":"before","run_ids":["run-LotOV1001"],"lot_count":1,"wafer_count":2,"budgets":[...]},"after":{"period":"after","run_ids":["run-LotOV1003"],"lot_count":1,"wafer_count":2,"budgets":[...]},"budgets":[{"budget":"nce_wafer.average","before_x":0.75,"after_x":1.52,"delta_x":0.77,"delta_x_pct":102.7,"before_y":0.62,"after_y":0.81,"delta_y":0.19,"delta_y_pct":30.6}],"largest_increase":{"budget":"nce_wafer.average","axis":"X","delta":0.77,"delta_pct":102.7},"headline":"Largest increase: NCE - Wafer · Average X +102.7%"}
```
