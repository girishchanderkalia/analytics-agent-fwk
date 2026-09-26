# Deployable mock Analytics Foundation service

The service implements the Slice 13A HTTP contract over file-backed JSON repositories. The bundled data files are intentionally empty. Deployments must mount approved mock datasets as `trend_rows.json` and `wafer_rows.json` under `ANALYTICS_FOUNDATION_DATA_DIR`.

Both MCP tools and deterministic application BFF clients must consume this service over HTTP. They must not import this repository implementation.
