---
id: overlay-analysis-knowledge
version: "1.0"
kind: knowledge-model
concepts:
  overlay:
    description: Lot-level measured overlay, with separate X and Y values for the selected metric.
evidence_labels:
  overlay_analysis:
    description: Answer grounded in the displayed measurement snapshot, with limitations.
---

# Overlay Evidence

Foundation joins lot steps, exposure steps, metrology steps, LOT KPI mappings,
overlay KPI values and exposure-machine labels. Missing timestamps or KPI values
remain null. Neither measurement units nor a causal explanation are implied.