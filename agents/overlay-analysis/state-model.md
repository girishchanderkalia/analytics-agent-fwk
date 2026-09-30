---
id: overlay-analysis-state
version: "1.0"
kind: state-model
fields:
  question:
    type: string
    default: ""
  conversation_context:
    type: object
    default: {}
  current_activity:
    type: optional_string
    default: null
  overlay_analysis:
    type: object
    default: null
---

# Overlay State

The application snapshot and question are inputs. `overlay_analysis` contains
the structured answer and limitations returned to the chat panel.