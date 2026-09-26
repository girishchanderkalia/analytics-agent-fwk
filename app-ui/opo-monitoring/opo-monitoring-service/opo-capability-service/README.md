# OPO Capability Service

A separately deployable, application-owned MCP service exposing the pure OPO calculations from Slice 13F. It performs no Analytics Foundation I/O and owns no graph, prompt, model, checkpoint, or registration behavior.

Tools: `analyze_trends`, `normalize_wafer_evidence`, and `classify_spatial_pattern`.

Run: `python -m uvicorn opo_capability_service.app:app --host 0.0.0.0 --port 8300`.
