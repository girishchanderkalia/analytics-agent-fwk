---
id: overlay-analysis-workflow
version: "1.0"
kind: workflow
entry_node: analyze_overlay
nodes:
  - id: analyze_overlay
    type: model
    prompt: overlay_answer
    output: OverlayAnswer
    output_to: overlay_analysis
    inputs:
      - question
      - conversation_context
    activity: Analyzing the displayed overlay measurements
edges:
  - from: analyze_overlay
    to: END
---

# Overlay Chat

The model interprets the analyst's question against the displayed X/Y snapshot.
This read-only workflow does not invoke OPO capabilities or modify chart filters.