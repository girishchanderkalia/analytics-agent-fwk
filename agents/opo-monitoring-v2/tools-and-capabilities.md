---
id: opo-monitoring-capabilities-v2
version: "2.0"
kind: tools-and-capabilities

operations:
  - id: normalize_trend_window
    server: opo-capability
    tool: normalize_trend_window
    version: "1"
    owner: OPO Monitoring application
    description: Apply the inclusive one-calendar-month window from the parsed start date.
    request:
      filters: ${state.trend_filters}
      question: ${state.question}
      available_scopes: ${state.conversation_context.available_trend_scopes}
    result:
      trend_filters: ${result.trend_filters}

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
    result:
      trend_series: ${result.series}
---

# V2 data boundaries

The OPO capability normalizes the model's trend window before the governed
Foundation query. No TDBB capability exists yet. Before/after budget bars and
wafer/field plots remain unavailable until Foundation publishes real data.