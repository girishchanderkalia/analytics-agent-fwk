# Deployable mock Analytics Foundation service

The service implements the Slice 13A HTTP contract over file-backed JSON repositories. By default it loads `trend_rows_v2.json` and `large_data/wafer_rows_v2.json` under `ANALYTICS_FOUNDATION_DATA_DIR`. Override `ANALYTICS_FOUNDATION_TREND_ROWS_FILE` or `ANALYTICS_FOUNDATION_WAFER_ROWS_FILE` to select another pair of files.

Both MCP tools and deterministic application BFF clients must consume this service over HTTP. They must not import this repository implementation.

## Lot-level overlay analysis

`POST /overlay/trends/query` reads the exported relational tables directly from the configured data directory. The existing `/trends` endpoints and datasets are unchanged. The nine LANA exports are included as `lot_step.json`, `lot_exposure_step.json`, `lot_metrology_step.json`, `lot_kpi_mapping.json`, `lot_metrology_overlay_kpis.json`, `exposure_machine.json`, `performance_domain.json`, `wafer_exposure_step.json`, and `wafer_metrology_step.json`. The last three are retained for reference, not joined into the lot-level query.

The query starts with lot steps, left-joins exposure and metrology steps, inner-joins metrology KPI mappings restricted to `LOT`, inner-joins overlay KPIs by mapping ID, and left-joins exposure machines. It removes duplicate grouped rows and orders by lot-step ID. KPI values come from the KPI table, not `lot_step.json` or the precomputed trend files.

```json
{
	"kpi": "MEASURED_OVERLAY",
	"metric": "MEAN",
	"start_date": "2026-01-01",
	"end_date": "2026-12-31",
	"product_ids": [],
	"excluded_product_ids": [],
	"lot_ids": [],
	"layer_ids": [],
	"exposure_equipment_ids": []
}
```

All fields are optional. With no dates, the full export is queried. Date bounds are inclusive on exposure `lot_start`; other filters use exact matches. Invalid metrics, dates, and reversed date ranges return 422. Missing datasets return 503.

| Metric | X / Y column prefix |
| --- | --- |
| MAX | `measured_raw_max` |
| MIN | `measured_raw_min` |
| MEAN (default) | `measured_raw_mean` |
| M3S | `measured_raw_m3s` |
| MAX_997 | `filtered_raw_99_7` |

Each prefix is suffixed with `_x` or `_y`. The response contains `kpi`, `metric`, and `points`, with exposure identifiers/timestamps, metrology identifiers, `kpi_x`, `kpi_y`, and `needs_ingestion: false`. Missing exposure fields and KPI values remain null, never zero-filled. API values retain source precision and units; the UI table displays four decimal places and CSV retains source precision.

The original `rounded`, `buildWhereClause`, and `EXPOSURE_EQUIPMENT_ID_COLUMN` helpers were not supplied. Consequently no server-side rounding or unit conversion is assumed; exposure labels use nonempty `customername` with machine ID fallback, and filtering follows the rules above. Wafer KPI analysis is not implemented by this endpoint.
