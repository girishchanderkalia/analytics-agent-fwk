# Slice 13K end-to-end integration tests

This package validates the deployed boundaries built in Slices 13A through 13J.
It is intentionally black-box and calls public HTTP endpoints only.

The default suite runs health, discovery, deterministic BFF, and architecture
checks. Model-backed chat tests are enabled with `RUN_AGENT_E2E=true` so that
normal local validation does not require model credentials.
