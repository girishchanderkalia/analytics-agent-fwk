---
id: opo-monitoring-capabilities
version: "1.0"
kind: tools-and-capabilities

approvals:
  default: deny
  required_for:
    - workspace.register_dataset

operations:
  - id: analyse_trends
    server: opo-capability
    tool: analyze_trends
    version: "1"
    owner: OPO Monitoring application
    description: >
      Application-owned threshold and outlier rules, reached through the
      framework's MCP tool boundary.

    request:
      series: ${state.trend_series}
      mode: ${state.detection_scope.mode}
      limit_value: ${state.detection_scope.limit_value}
      direction: ${state.detection_scope.direction}
      baseline_deviation_pct: ${state.detection_scope.baseline_deviation_pct}
      limit_unit: ${state.detection_scope.threshold_unit}

    result:
      analysis: ${result.analysis}
      outliers: ${result.outliers}

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

  - id: data_query.read_distribution_stats
    operation: read_distribution_stats
    server: analytics-foundation
    tool: get_distribution_stats
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
      threshold_context: ${result}

  - id: workspace.create
    operation: create_workspace
    server: analytics-foundation
    tool: create_workspace
    owner: Analytics Foundation
    version: "1"

    permissions:
      - workspace:create

    side_effect: true
    approval_required: false

    request: {}

    result:
      workspace: ${result}

  - id: workspace.add_filters
    operation: add_filters
    server: analytics-foundation
    tool: add_workspace_filters
    owner: Analytics Foundation
    version: "1"

    permissions:
      - workspace:write

    side_effect: true
    approval_required: false

    request:
      workspace_id: ${state.workspace.workspace_id}
      filters: ${state.trend_filters}

    result:
      applied_filters: ${result}

  - id: workspace.register_dataset
    operation: register_dataset
    server: analytics-foundation
    tool: register_dataset
    owner: Analytics Foundation
    version: "1"

    permissions:
      - workspace:register

    side_effect: true
    approval_required: true

    request:
      workspace_id: ${state.workspace.workspace_id}
      dataset: overlay
      table: overlay_wafer_points

    result:
      registration: ${result}

  - id: data_query.read_wafers
    operation: read_wafers
    server: analytics-foundation
    tool: query_wafers
    owner: Analytics Foundation
    version: "1"

    permissions:
      - query:wafers:read

    side_effect: false
    approval_required: false

    request:
      workspace_id: ${state.workspace.workspace_id}
      table: ${state.registration.table}
      filters: {}

    result:
      wafer_rows: ${result.rows}
      anomalous_wafers: ${result.anomalous_wafers}
---

# OPO Monitoring Tools and Capabilities

Capabilities describe the contract between the OPO Monitoring Agent and the
shared Application Agent Runtime.

The Capability Adaptor is owned by the Application Agent Runtime. The
Capability Adaptor translates logical agent capability requests into Analytics
Foundation API requests.

## Capability summary

| Operation | Capability | Side effect | Approval |
| --- | --- | --- | --- |
| Read OPO KPI trends | `data_query.read_trends` | No | No |
| Create investigation workspace | `workspace.create` | Yes | No |
| Apply workspace filters | `workspace.add_filters` | Yes | No |
| Register wafer data | `workspace.register_dataset` | Yes | Yes |
| Read wafer evidence | `data_query.read_wafers` | No | No |

## Runtime invocation rules

For each invocation, the runtime must:

1. Confirm that the capability is declared by the agent.
2. Resolve the capability from the Capability Registry.
3. Map workflow state into the declared request.
4. Validate the mapped request.
5. Verify required permissions.
6. Verify approval when required.
7. Record the capability invocation.
8. Invoke the configured Analytics Foundation client.
9. Record success or failure.
10. Map the declared result into workflow state.

## Boundary rules

The agent must not directly access:

- PostgreSQL
- StarRocks
- HDFS
- object storage
- Analytics Foundation service databases
- Analytics Foundation internal implementation classes

The OPO Monitoring Service may call Analytics Foundation APIs directly for
existing deterministic application functions.

Only Analytics Foundation operations originating from an agent workflow use
the runtime-owned Capability Adaptor.