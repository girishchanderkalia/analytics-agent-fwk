---
id: opo-monitoring-capabilities-v2
version: "2.0"
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
    result:
      trend_series: ${result.series}
---

# V2 data boundaries

The model extracts the one-month trend window and requests the read-only
Foundation `query_trends` tool. No TDBB capability exists yet. Before/after
budget bars and wafer/field plots remain unavailable until Foundation publishes
real data.