---
id: opo-monitoring-capabilities-v3
version: "3.0"
kind: tools-and-capabilities

capabilities:
  - id: data_query.read_trends
    operation: query_trends
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

  - id: processing.run_tdbb_before
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
      start_date: ${state.comparison_scope.change_date}
      end_date: ${state.trend_filters.end_date}
      change_date: ${state.trend_filters.end_date}
      lot_ids: ${state.trend_filters.lot_ids}
      product_ids: ${state.trend_filters.product_ids}
      layer_ids: ${state.trend_filters.layer_ids}
      exposure_equipment_ids: ${state.trend_filters.exposure_equipment_ids}
      chuck_ids: ${state.trend_filters.chuck_ids}
    result:
      tdbb_run: ${result}
---

# V3 data boundaries

The model extracts the trend window and requests `query_trends` through the
read-only Foundation tool. TDBB runs through Analytics Foundation with its
default settings (10par, AVG and W2W), one run for each period; the model
compares the returned evidence.
