# OPO response compatibility

This package preserves the existing OPO UI-facing response contract while the
backend moves to the shared declarative runtime.

It is a pure projection layer. It does not invoke tools, access Foundation,
construct graphs, write checkpoints, or record audit events.
